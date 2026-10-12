"""Forward paper books for the shadow lab (shorts + leverage, PAPER ONLY, never the live book). Deterministic and idempotent: each run replays each lab
book from its start day over the closed days to date using lab.run (same model as the backtest), then writes lab-scoreboard.json.
Each book starts at A$500 on START. A liquidated book stays at 0. python3 lab_trial.py"""
import json, time
from pathlib import Path
import engine, lab
H = Path(__file__).parent; START = "2026-10-12"
BOOKS = {"LAB1-trend-ls-3x": ("trend_ls", {"k": 5, "n": 50, "tvol": 0.04}, 3.0), "LAB2-btc-ls-3x": ("btc_ls", {"n": 50}, 3.0),
         "LAB3-moon-long-3x": ("moon_long", {"n": 7, "thr": 0.15}, 3.0), "LAB4-trend-ls-2x": ("trend_ls", {"k": 5, "n": 50, "tvol": 0.04}, 2.0),
         "LAB5-knife-short-3x": ("knife_short", {"thr": 0.25, "max": 4}, 3.0)}
def books():
    b = dict(BOOKS); f = H / "lab-books.json"            # books spawned by improve.py from the lab tournament (frozen configs, own start days)
    if f.exists():
        for cid, v in json.loads(f.read_text()).items(): b[cid] = (v["family"], v["params"], v["leverage"], v["start"])
    return b
def main():
    P = engine.Panel(); HL = lab.hilo(P); s = next((i for i, d in enumerate(P.dates) if d[:10] >= START), None); out = []
    for cid, spec in books().items():
        fam, par, L = spec[:3]; st = spec[3] if len(spec) > 3 else START
        s = next((i for i, d in enumerate(P.dates) if d[:10] >= st), None)
        if s is None or s >= len(P.dates) - 1: out.append({"id": cid, "family": fam, "leverage": L, "days": 0, "equity": 500.0, "return_pct": 0.0, "max_drawdown_pct": 0.0, "ruined": False}); continue
        path, ruin = lab.run(P, HL, fam, par, L, s, len(P.dates)); pk, dd = 500.0, 0.0
        for e in path: pk = max(pk, e); dd = min(dd, e / pk - 1)
        out.append({"id": cid, "family": fam, "leverage": L, "days": len(path) - 1, "equity": round(path[-1], 2), "return_pct": round((path[-1] / 500 - 1) * 100, 2), "max_drawdown_pct": round(dd * 100, 2), "ruined": ruin})
    res = {"label": "PAPER ONLY - shadow lab: shorts and leverage, modelled with verified Independent Reserve costs (0.5% fee + 0.1% slippage per side, 0.05%/day long interest on the borrowed part, 0.03%/day short). Never the live book.",
           "asof": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "start": START, "target": "A$1000 (+100%)", "books": sorted(out, key=lambda b: -b["equity"])}
    (H / "lab-scoreboard.json").write_text(json.dumps(res, indent=1))
    for b in res["books"]: print("%-22s %dx days %2d equity %7.2f %s" % (b["id"], b["leverage"], b["days"], b["equity"], "RUINED" if b["ruined"] else ""))
main()
