"""Week 1 driver: runs the baseline allocator on every size distribution.

Usage: python3 run_week1.py [--heap 262144] [--ops 10000] [--seeds 5]
                            [--util 0.7] [--out week1_results.csv]
"""
import argparse
import csv
import statistics

from simulator import run
from workload import DISTS, generate_trace, mean_size

ALIGN = 8
METRICS = ("mean_ext_frag", "failure_rate", "mean_alloc_visits", "mean_util", "mean_blocks")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--heap", type=int, default=262144)
    ap.add_argument("--ops", type=int, default=10000)
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--util", type=float, default=0.7, help="target utilization")
    ap.add_argument("--sample", type=int, default=50)
    ap.add_argument("--out", default="week1_results.csv")
    args = ap.parse_args()

    rows = []
    print(f"baseline (first-fit, no coalescing): heap={args.heap}, ops={args.ops}, "
          f"seeds={args.seeds}, target util={args.util}")
    print(f"{'dist':8s} {'ext_frag':>9s} {'fail_rate':>10s} {'visits/alloc':>13s} "
          f"{'util':>6s} {'free_blocks':>12s}")
    for dist in DISTS:
        target = max(1, int(args.util * args.heap / mean_size(dist, ALIGN)))
        per_metric = {m: [] for m in METRICS}
        for seed in range(1, args.seeds + 1):
            trace = generate_trace(args.ops, seed, dist, target)
            res = run(trace, args.heap, align=ALIGN, sample_every=args.sample,
                      warmup_ops=target)
            row = {"dist": dist, "seed": seed, "attempts": res.attempts,
                   "fail_frag": res.fail_frag, "fail_oom": res.fail_oom}
            for m in METRICS:
                row[m] = getattr(res, m)
                per_metric[m].append(row[m])
            rows.append(row)
        mean = {m: statistics.fmean(v) for m, v in per_metric.items()}
        print(f"{dist:8s} {mean['mean_ext_frag']:9.3f} {mean['failure_rate']:10.4f} "
              f"{mean['mean_alloc_visits']:13.1f} {mean['mean_util']:6.3f} "
              f"{mean['mean_blocks']:12.1f}")

    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
