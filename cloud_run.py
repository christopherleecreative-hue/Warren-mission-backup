"""Cloud backup runner (GitHub Actions, free, no AI, no secrets): rebuilds every spot and lab book from public BTC Markets prices and writes results/. Stateless: the books are a pure
replay from each start date, so a fresh checkout gives the same numbers as the Mac. Books that need the Mac's 103-coin store (WIDE*) are skipped here. python3 cloud_run.py"""
import json, shutil, sys, time
from pathlib import Path
H = Path(__file__).parent; sys.path.insert(0, str(H)); (H / "state").mkdir(exist_ok=True); (H / "data").mkdir(exist_ok=True)
import data
data.refresh("1d", days=900)                       # 900 days: enough for the 200-day regime and 250-day Donchian lookbacks
import trial, lab_trial                            # lab_trial runs on import (writes lab-scoreboard.json)
trial.run(fetch=False)
R = H / "results"; R.mkdir(exist_ok=True)
for f in ("scoreboard.json", "scoreboard.md", "lab-scoreboard.json"):
    if (H / f).exists(): shutil.copy2(H / f, R / f)
sb = json.loads((R / "scoreboard.json").read_text()); lb = json.loads((R / "lab-scoreboard.json").read_text())
best = max(sb["books"] + lb["books"], key=lambda b: b.get("equity", 0))
(R / "STATUS.md").write_text("# Warren mission cloud backup\n\nRun %s UTC. Paper only. Goal A$500 to A$1,000 by 11 Nov 2026.\n\nBest book here: %s at A$%.2f (%s days). Books needing the Mac's 103-coin store (WIDE1-4) are not run in the cloud.\n\nFiles: scoreboard.md, scoreboard.json, lab-scoreboard.json.\n" % (time.strftime("%Y-%m-%d %H:%M", time.gmtime()), best["id"], best["equity"], best.get("days", 0)))
print("cloud run ok; best:", best["id"], best["equity"])
