"""Daily shadow-trial runner. PAPER ONLY, own ledger (state/trials.sqlite3), never touches the live book. Idempotent per (candidate, day):
re-running the same day changes nothing. Each candidate starts at A$500 on its start day with the live book's costs (engine.COST per side).
Usage: python3 trial.py [--no-fetch]   -> refreshes candles, books any closed days not yet booked, writes scoreboard.json/.md"""
import json, sqlite3, sys, time
from pathlib import Path
import data, engine, strategies
HERE = Path(__file__).parent; (HERE / "state").mkdir(exist_ok=True); DB = HERE / "state/trials.sqlite3"; REG = HERE / "candidates.json"

def db():
    c = sqlite3.connect(DB)
    c.executescript("""create table if not exists books(cid text, day text, equity real, target text, turnover real, primary key(cid, day));
    create table if not exists cands(cid text primary key, family text, params text, started text, status text, note text);""")
    return c

def registry():
    """candidates.json holds frozen configs (id -> family, params, start day). Seeded from strategies.CANDIDATES on first run."""
    if REG.exists(): return json.loads(REG.read_text())
    return {}

def wide_panel():
    """Wider coin list (103 AUD markets incl. Swyftx-only coins like QNT) from the node engine's store, read-only."""
    import sqlite3
    from collections import defaultdict
    db = Path.home() / ".codex/.chatgpt-projects/g-p-6aafdc1e1c6c8191977220ca2f3b5914/bill-setup/warren-upgrade/node_engine/state/nodes.sqlite3"
    con = sqlite3.connect("file:%s?mode=ro" % db, uri=True); raw = defaultdict(list)
    for m, ts, o, h, l, c_, v in con.execute("select market,ts,o,h,l,c,v from candles where tf='1d' and market like '%-AUD' order by ts"):
        raw[m.split("-")[0]].append([ts[:10] + "T00:00:00.000000Z", o, h, l, c_, v or 0])
    return engine.Panel(raw={k: v for k, v in raw.items() if k not in ("USDT", "USDC", "AUDM", "RLUSD", "XAUT", "DAI")})

def run(fetch=True):
    if fetch: data.refresh("1d", days=200)
    P0 = engine.Panel(); PW = None; c = db(); reg = registry(); today = P0.dates[-1]
    for cid, spec in reg.items():
        if spec["status"] != "active": continue
        wide = spec.get("universe") == "wide"
        if wide and not (Path.home() / ".codex/.chatgpt-projects/g-p-6aafdc1e1c6c8191977220ca2f3b5914/bill-setup/warren-upgrade/node_engine/state/nodes.sqlite3").exists(): continue   # cloud backup has no 103-coin store: skip wide books there
        if wide and PW is None: PW = wide_panel()
        P = PW if wide else P0; COST = spec.get("cost", engine.COST)
        f = strategies.FAMILIES[spec["family"]]; par = spec["params"]
        start = spec["start"]; last = c.execute("select max(day), equity from books where cid=?", (cid,)).fetchone()
        eq = last[1] if last[0] else 500.0
        w = {}
        if last[0]: w = json.loads(c.execute("select target from books where cid=? and day=?", (cid, last[0])).fetchone()[0])
        P.state = {}
        # warm indicator state by replaying signals (not equity) from 60 days before start
        i0 = max(0, P.dates.index(next(d for d in P.dates if d >= start)) - 60) if start in P.dates or any(d >= start for d in P.dates) else 0
        for i in range(i0, len(P.dates) - 1):
            tgt = f(P, i, par) or {}
            if par.get("reb") and (P.dn[i] % par["reb"]): tgt = P_prev if i > i0 else {}
            P_prev = tgt
            day = P.dates[i + 1]
            if day < start or (last[0] and day <= last[0]): continue
            turn = sum(abs(tgt.get(k, 0) - w.get(k, 0)) for k in set(tgt) | set(w))
            eq *= 1 - COST * turn
            g = sum(x * (P.close[k][i + 1] / P.close[k][i] - 1) for k, x in tgt.items() if P.close[k][i] and P.close[k][i + 1])
            eq *= 1 + g; w = tgt
            c.execute("insert or ignore into books values(?,?,?,?,?)", (cid, day, eq, json.dumps(tgt), turn))
    c.commit(); scoreboard(c, reg, P0)

def scoreboard(c, reg, P):
    rows = []
    for cid, spec in reg.items():
        h = c.execute("select day, equity from books where cid=? order by day", (cid,)).fetchall()
        if not h: rows.append({"id": cid, "status": spec["status"], "days": 0, "equity": 500.0}); continue
        pk, dd = 500.0, 0.0
        for _, e in h: pk = max(pk, e); dd = min(dd, e / pk - 1)
        rows.append({"id": cid, "family": spec["family"], "status": spec["status"], "start": spec["start"], "days": len(h), "last_day": h[-1][0],
                     "equity": round(h[-1][1], 2), "return_pct": round((h[-1][1] / 500 - 1) * 100, 2), "max_drawdown_pct": round(dd * 100, 2)})
    rows.sort(key=lambda r: -r.get("equity", 0))
    out = {"label": "PAPER ONLY - shadow trials, not the live book; net of 0.5% fee + 0.5% slippage per side; day-close data (BTC Markets AUD)",
           "asof": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "target": "A$1000 (+100%) within 30 days of mission start", "books": rows}
    (HERE / "scoreboard.json").write_text(json.dumps(out, indent=1))
    L = ["# Warren profit mission scoreboard", "", out["label"], "", "As of " + out["asof"], "", "| Candidate | Days | Equity A$ | Return % | Max DD % |", "|---|---|---|---|---|"]
    L += ["| %s | %s | %s | %s | %s |" % (r["id"], r["days"], r["equity"], r.get("return_pct", "-"), r.get("max_drawdown_pct", "-")) for r in rows]
    (HERE / "scoreboard.md").write_text("\n".join(L) + "\n")
    print("\n".join(L[6:]))

if __name__ == "__main__":
    run(fetch="--no-fetch" not in sys.argv)
