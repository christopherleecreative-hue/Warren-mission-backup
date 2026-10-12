# Warren mission cloud backup

Paper only. A free GitHub Actions job that rebuilds Warren's 30-day profit mission books (goal A$500 to A$1,000 by 11 Nov 2026) from public BTC Markets prices every day at 00:40 UTC. No AI, no keys, no secrets. Results appear in `results/` (`STATUS.md`, `scoreboard.md`, `lab-scoreboard.json`). The books are a pure replay from each start date, so this repo keeps no state and gives the same numbers as the Mac. Books needing the Mac's 103-coin store (WIDE1-4) are not run here. The Mac stays the main system.
