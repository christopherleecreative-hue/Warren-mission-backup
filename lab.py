"""SHADOW LAB: paper shorts and leverage (Chris approved 12 Oct 2026, lab only, never the live book). PAPER ONLY, no exchange, no account.
Instrument model, costs VERIFIED 12 Oct 2026 from Independent Reserve's own fees page (https://www.independentreserve.com/fees, read at source):
  trading fee 0.50% per trade at our volume (falls to 0.02% only at A$200m/30 days), plus 0.1% assumed slippage = 0.6% per side;
  leverage longs pay 0.05% per day interest on the BORROWED part, leverage shorts pay 0.03% per day on the notional; open/close free;
  mandatory liquidation fee 1% of the loan. AUD spot candles are the price proxy. Leverage capped at 3x; liquidation when equity falls to 10%
  of its start (checked against the day's intraday high/low, adverse side); a liquidated book is worth 0 for the rest of its run.
Backtest: every 30-day window starts a fresh A$500 book; stats = median, p10, p90, share touching +100%, share ending >= +100%, ruin rate.
python3 lab.py -> state/lab.json (first 60% fit, last 40% holdout)"""
import json, time
from pathlib import Path
import data, engine, strategies
H = Path(__file__).parent
COST, FUND_LONG, FUND_SHORT, MAINT, LMAX = 0.006, 0.0005, 0.0003, 0.10, 3.0
def hilo(P):
    raw = data.load("1d"); ix = {d: i for i, d in enumerate(P.dates)}
    hi = {c: [None] * len(P.dates) for c in raw}; lo = {c: [None] * len(P.dates) for c in raw}
    for c, rows in raw.items():
        for r in rows:
            if r[0] in ix: hi[c][ix[r[0]]] = r[2]; lo[c][ix[r[0]]] = r[3]
    return hi, lo
def norm(w):
    t = sum(abs(v) for v in w.values()); return {c: v / t for c, v in w.items()} if t > 1 else w
def topliquid(P, i, k): 
    return sorted(strategies.liquid(P, i), key=lambda c: -sum(P.close[c][j] * P.vol[c][j] for j in range(i - 13, i + 1) if P.close[c][j]))[:k]
def vol20(x, i):
    r = [x[j] / x[j - 1] - 1 for j in range(i - 19, i + 1) if x[j] and x[j - 1]]
    if len(r) < 15: return None
    m = sum(r) / len(r); return (sum((v - m) ** 2 for v in r) / len(r)) ** .5
def trend_ls(P, i, p):                       # long above SMA, short below, vol-sized, top-k liquid
    w = {}
    for c in topliquid(P, i, p["k"]):
        x = P.close[c]; s = strategies.sma(x, i, p["n"]); v = vol20(x, i)
        if s and v and x[i]: w[c] = (1 if x[i] > s else -1) * min(1.0, p["tvol"] / v) / p["k"]
    return norm(w)
def knife_short(P, i, p):                    # short coins that fell > thr over 14d (the one significant pattern); flat otherwise
    w = {}
    for c in strategies.liquid(P, i):
        if i >= 15 and strategies.ret(P, c, i, 14) is not None and strategies.ret(P, c, i, 14) < -p["thr"]: w[c] = -1
    w = dict(sorted(w.items())[:p["max"]]); return {c: -1 / p["max"] for c in w}
def xs_ls(P, i, p):                          # long strongest k, short weakest k by n-day return
    r = sorted(((strategies.ret(P, c, i, p["n"]), c) for c in strategies.liquid(P, i) if i >= p["n"] and strategies.ret(P, c, i, p["n"]) is not None))
    if len(r) < 2 * p["k"]: return {}
    return norm({**{c: 1 / (2 * p["k"]) for _, c in r[-p["k"]:]}, **{c: -1 / (2 * p["k"]) for _, c in r[:p["k"]]}})
def btc_ls(P, i, p):                         # BTC only, trend long/short
    s = strategies.sma(P.close["BTC"], i, p["n"]); x = P.close["BTC"][i]
    return {"BTC": 1 if x > s else -1} if s and x else {}
def moon_long(P, i, p):                      # leveraged concentrated breakout long
    best = None
    for c in strategies.liquid(P, i, min_aud=5000):
        r = strategies.ret(P, c, i, p["n"])
        if r is not None and r > p["thr"] and (best is None or r > best[0]): best = (r, c)
    return {best[1]: 1} if best else {}
FN = {"trend_ls": trend_ls, "knife_short": knife_short, "xs_ls": xs_ls, "btc_ls": btc_ls, "moon_long": moon_long}
def run(P, HL, fam, par, L, start, end, eq=500.0):
    """Returns (final equity multiple path list, ruined). Fresh book from `start` to `end`."""
    hi, lo = HL; w = {}; path = [eq]
    for i in range(start, min(end, len(P.dates) - 1)):
        tgt = FN[fam](P, i, par) or {}
        x = {c: L * v for c, v in tgt.items()}; pw = {c: L * v for c, v in w.items()}
        turn = sum(abs(x.get(c, 0) - pw.get(c, 0)) for c in set(x) | set(pw)); fund = sum((max(v - 1, 0) * FUND_LONG if v > 0 else abs(v) * FUND_SHORT) for v in x.values())
        eq *= 1 - turn * COST - fund
        worst = 0.0; ret = 0.0
        for c, e in x.items():
            p0, p1 = P.close[c][i], P.close[c][i + 1]
            if not p0 or not p1: continue
            ret += e * (p1 / p0 - 1)
            ext = lo[c][i + 1] if e > 0 else hi[c][i + 1]
            if ext: worst += e * (ext / p0 - 1)
        if 1 + worst <= MAINT:
            path.append(0.0); return path, True
        eq *= 1 + ret
        if eq <= 0: path.append(0.0); return path, True
        path.append(eq); w = tgt
    return path, False
def stats(P, HL, fam, par, L, lo_i, hi_i, days=30, step=3):
    res = []
    for s in range(lo_i, hi_i - days, step):
        path, ruin = run(P, HL, fam, par, L, s, s + days); res.append((path[-1] / 500, max(path) / 500, ruin))
    if not res: return {}
    f = sorted(r[0] for r in res); q = lambda p: f[int(p * (len(f) - 1))]
    return {"windows": len(res), "median": round(q(.5) - 1, 3), "p10": round(q(.1) - 1, 3), "p90": round(q(.9) - 1, 3), "touch_ge_100pct": round(sum(r[1] >= 2 for r in res) / len(res), 3),
            "end_ge_100pct": round(sum(r[0] >= 2 for r in res) / len(res), 3), "ruin_rate": round(sum(r[2] for r in res) / len(res), 3)}
LAB = {"LS1-trend-ls-k5": ("trend_ls", {"k": 5, "n": 50, "tvol": 0.04}), "LS2-knife-short": ("knife_short", {"thr": 0.25, "max": 4}),
       "LS3-xs-ls-k3": ("xs_ls", {"n": 14, "k": 3}), "LS4-btc-ls": ("btc_ls", {"n": 50}), "LS5-moon-long": ("moon_long", {"n": 7, "thr": 0.15})}
if __name__ == "__main__":
    P = engine.Panel(); HL = hilo(P); n = len(P.dates); cut = int(n * .6); first = 120; out = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "assumptions": {"source": "independentreserve.com/fees read 12 Oct 2026", "cost_per_side": COST, "funding_long_per_day_on_borrowed": FUND_LONG, "funding_short_per_day": FUND_SHORT, "maint": MAINT, "lmax": LMAX}, "results": []}
    for cid, (fam, par) in LAB.items():
        for L in (1.0, 2.0, 3.0):
            fit = stats(P, HL, fam, par, L, first, cut); ho = stats(P, HL, fam, par, L, cut, n)
            out["results"].append({"id": cid, "leverage": L, "fit": fit, "holdout": ho})
            print("%-18s %dx  FIT med %+4.0f%% touch %4.1f%% ruin %4.1f%% | HOLDOUT med %+4.0f%% p10 %+4.0f%% p90 %+4.0f%% touch100 %4.1f%% end100 %4.1f%% ruin %4.1f%%" % (cid, L, fit["median"] * 100, fit["touch_ge_100pct"] * 100, fit["ruin_rate"] * 100, ho["median"] * 100, ho["p10"] * 100, ho["p90"] * 100, ho["touch_ge_100pct"] * 100, ho["end_ge_100pct"] * 100, ho["ruin_rate"] * 100), flush=True)
    (H / "state/lab.json").write_text(json.dumps(out, indent=1))
