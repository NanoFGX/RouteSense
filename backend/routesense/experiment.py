"""The replay experiment for Chapter 5.

    python -m routesense.experiment                       # 10 days x 5 replays (quick, ~4 min)
    python -m routesense.experiment --days 30 --replays 30   # the full design (~2 h)

Every strategy plays the same random Klang Valley days with the same random
draws (same seed per day and replay), so the comparison is paired. Results go
to backend/results/experiment.csv and a summary with Wilcoxon signed-rank tests
is printed.
"""

from __future__ import annotations

import argparse
import csv
import statistics

from scipy.stats import wilcoxon

from . import config
from .demo_day import random_day
from .planner import STRATEGIES
from .risk.model import get_model
from .simulator import simulate_day
from .travel import default_provider

FIELDS = ["day", "replay", "strategy", "parcels", "delivered", "delivered_first_try", "failed_attempts",
          "carried_over", "unpaid_min", "km", "finish_min", "active_min", "free_min", "replies"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=10)
    ap.add_argument("--replays", type=int, default=5)
    ap.add_argument("--stops", type=int, default=15)
    ap.add_argument("--scenario", default="mid", choices=["low", "mid", "high"])
    ap.add_argument("--reply-rate", type=float, default=config.DEFAULT_REPLY_RATE)
    args = ap.parse_args()

    model, travel = get_model(), default_provider()
    rows = []
    for d in range(args.days):
        day = random_day(1000 + d, args.stops, args.scenario)
        for r in range(args.replays):
            for strat in STRATEGIES:
                res = simulate_day(day, strat, seed=d * 100 + r, reply_rate=args.reply_rate, travel=travel, model=model)
                rows.append({"day": d, "replay": r, **{k: res[k] for k in FIELDS if k in res}})
        print(f"day {d + 1}/{args.days} done")

    out = config.BACKEND_DIR / "results"
    out.mkdir(exist_ok=True)
    with open(out / "experiment.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    def series(strat, key):
        return [r[key] for r in rows if r["strategy"] == strat]

    print(f"\n{args.days} days x {args.replays} replays, {args.stops} stops, scenario {args.scenario}, "
          f"reply rate {args.reply_rate:.0%}")
    keys = ["delivered", "delivered_first_try", "failed_attempts", "carried_over", "unpaid_min", "km"]
    print("strategy".ljust(22) + "".join(k[:14].rjust(16) for k in keys))
    for strat in STRATEGIES:
        print(strat.ljust(22) + "".join(f"{statistics.mean(series(strat, k)):16.2f}" for k in keys))

    print("\nPaired Wilcoxon signed-rank tests")
    for a, b in (("time_optimal", "routesense"), ("time_optimal", "routesense_replies"), ("routesense", "routesense_replies")):
        for key in ("delivered", "failed_attempts"):
            x, y = series(a, key), series(b, key)
            if any(i != j for i, j in zip(x, y)):
                stat, p = wilcoxon(x, y)
                print(f"  {key:<16} {a} vs {b}: mean {statistics.mean(x):.2f} vs {statistics.mean(y):.2f}, p = {p:.2g}")
    print(f"\nRows saved to {out / 'experiment.csv'}")


if __name__ == "__main__":
    main()
