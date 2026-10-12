"""Daily-bar paper engine shared by backtest and live shadow trials. Costs = the live book's: 0.5% fee + 0.5% slippage per side."""
import data, strategies, time
from datetime import datetime, timezone
COST = 0.01

class Panel:
    def __init__(self, tw="1d", raw=None):
        raw = raw or data.load(tw)
        self.dates = sorted({r[0] for rows in raw.values() for r in rows})
        ix = {d: n for n, d in enumerate(self.dates)}
        self.coins = sorted(raw)
        self.close = {c: [None] * len(self.dates) for c in raw}; self.vol = {c: [0.0] * len(self.dates) for c in raw}
        for c, rows in raw.items():
            for r in rows: self.close[c][ix[r[0]]] = r[4]; self.vol[c][ix[r[0]]] = r[5]
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        if self.dates and self.dates[-1][:10] >= today:       # today's candle is still forming: closed days only
            self.dates = self.dates[:-1]
            for c in raw: self.close[c] = self.close[c][:-1]; self.vol[c] = self.vol[c][:-1]
        self.dn = [int(datetime.strptime(d[:10], '%Y-%m-%d').replace(tzinfo=timezone.utc).timestamp() // 86400) for d in self.dates]  # absolute day number
        self.state = {}

def simulate(P, family, params, start, end, equity=500.0):
    """Hold weights from close i to close i+1. Returns equity curve [(date, equity)]; trades cost COST * |dw| * equity."""
    f = strategies.FAMILIES[family]; P.state = {}; w = {}; curve = []
    for i in range(max(start, 0), min(end, len(P.dates) - 1)):
        tgt = f(P, i, params) or {}
        if params.get('reb') and (P.dn[i] % params['reb']): tgt = w          # slow rebalance: keep last target between rebalance days
        turn = sum(abs(tgt.get(c, 0) - w.get(c, 0)) for c in set(tgt) | set(w))
        equity *= 1 - COST * turn
        g = 0.0
        for c, x in tgt.items():
            a, b = P.close[c][i], P.close[c][i + 1]
            g += x * (b / a - 1) if a and b else 0.0
        equity *= 1 + g
        # drift of weights ignored (rebalanced to target daily): simple, slightly cost-conservative
        w = tgt; curve.append((P.dates[i + 1], equity))
    return curve

def window_stats(curve, days=30):
    """Return distribution over every rolling `days` window: median, p10, p90, share >= +100%, worst drawdown."""
    v = [e for _, e in curve]; r = sorted(v[k + days] / v[k] - 1 for k in range(len(v) - days))
    if not r: return {}
    pk, dd = v[0], 0
    for x in v: pk = max(pk, x); dd = min(dd, x / pk - 1)
    q = lambda p: r[int(p * (len(r) - 1))]
    touch = sum(max(v[k + 1:k + days + 1]) / v[k] >= 2 for k in range(len(v) - days)) / len(r)
    return {"touch_ge_100pct": round(touch, 3), "windows": len(r), "median": round(q(.5), 3), "p10": round(q(.1), 3), "p90": round(q(.9), 3), "max": round(r[-1], 3),
            "share_ge_100pct": round(sum(x >= 1 for x in r) / len(r), 3), "max_drawdown": round(dd, 3), "total": round(v[-1] / v[0] - 1, 3)}
