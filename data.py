"""Public BTC Markets AUD candles (keyless, read-only). Cached under data/. python3 data.py [1d|1h]"""
import json, sys, time, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
D = Path(__file__).parent / "data"
API = "https://api.btcmarkets.net/v3/markets"

def get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "warren-mission/1"}), timeout=20) as r:
                return json.load(r)
        except Exception:
            time.sleep(1.5 * (i + 1))
    raise RuntimeError("fetch failed " + url)

def markets():
    return sorted(m["baseAssetName"] for m in get(API) if m["quoteAssetName"] == "AUD" and m["status"] == "Online")

def candles(coin, tw, start, end):
    """[[ts, o, h, l, c, v], ...] ascending, chunked (API returns newest-first, <=1000 per call)."""
    step = timedelta(days=900) if tw == "1d" else timedelta(hours=900)
    out, t = {}, start
    while t < end:
        t2 = min(t + step, end)
        q = "%s/%s-AUD/candles?timeWindow=%s&from=%s&to=%s" % (API, coin, tw, t.strftime("%Y-%m-%dT%H:%M:%S.000Z"), t2.strftime("%Y-%m-%dT%H:%M:%S.000Z"))
        for r in get(q):
            out[r[0]] = [r[0]] + [float(x) for x in r[1:]]
        t = t2
    return [out[k] for k in sorted(out)]

def refresh(tw="1d", days=None):
    end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    days = days or (900 if tw == "1d" else 120)
    for c in markets():
        f = D / ("%s-%s.json" % (tw, c))
        try:
            rows = candles(c, tw, end - timedelta(days=days), end)
        except RuntimeError as e:
            print("skip", c, e); continue
        if rows:
            old = {r[0]: r for r in json.loads(f.read_text())} if f.exists() else {}
            old.update({r[0]: r for r in rows})        # merge: never shrink cached history
            f.write_text(json.dumps([old[k] for k in sorted(old)]))
    print("ok", tw, len(list(D.glob(tw + "-*.json"))))

def load(tw="1d"):
    return {f.stem.split("-", 1)[1]: json.loads(f.read_text()) for f in sorted(D.glob(tw + "-*.json"))}

if __name__ == "__main__":
    refresh(sys.argv[1] if len(sys.argv) > 1 else "1d")
