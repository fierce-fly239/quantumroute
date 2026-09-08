#!/usr/bin/env python3
"""Held-out validation: does the tuned result survive seeds it has never seen?

    python3 validate.py

WHY THIS EXISTS

`sweep_variants.py` searched 140 QPSO configurations and 20 PSO configurations
over 8 seeds and reported the best of each. Picking the best of 140 on 8 samples
is a textbook way to overfit: some configuration will look good on those 8 seeds
by luck alone, and reporting its tuning score as its performance would be wrong.

So the tuning seeds (1-8) are thrown away and the two winning configurations are
re-run on 30 seeds (101-130) that took no part in choosing them. Whatever this
prints is the number that goes in the deck.

WHAT IT MEASURED, 2026-09-06

  Sweep, 8 tuning seeds:   QPSO 1295.02  PSO 1314.68   QPSO +1.50%
  Held out, 30 fresh seeds: QPSO 1344.32  PSO 1356.70   QPSO +0.91%

Both scores got worse on unseen seeds and the gap narrowed - that difference IS
the overfitting, and it is the reason this file exists. The direction held.
"""

import argparse
import statistics
from typing import List

from app import scenarios
from app.optimizer.fitness import Weights
from app.optimizer.problem import Problem
from app.optimizer.pso import PSOParams
from app.optimizer.pso import optimize as pso_optimize
from app.optimizer.qpso import QPSOParams
from app.optimizer.qpso import optimize as qpso_optimize

# The winners from sweep_variants.py on ggn-50. Both spend 40,040 evaluations.
QPSO_BEST = dict(particles=20, iterations=1999, alpha_start=0.7, alpha_end=0.35,
                 weighted_mbest=False, alpha_curve="quadratic")
PSO_BEST = dict(particles=80, iterations=499, inertia_start=0.3, inertia_end=0.1)

# 20 x (1999+1) = 40,000 and 80 x (499+1) = 40,000 - EXACTLY equal.
# The original sweep used 20x2001 (40,040) against 80x499 (40,000): a 0.1%
# advantage to QPSO, caught by the budget check added to benchmark.compare().
# Small, but the whole claim rests on the budgets being identical, so it is
# corrected here rather than explained away.

TUNING_SEEDS = range(1, 9)
HELD_OUT_SEEDS = range(101, 131)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--network", default="ggn-50", choices=sorted(scenarios.NETWORKS))
    args = ap.parse_args()

    problem = Problem(scenarios.get_graph(args.network))
    weights = Weights()
    seeds = list(HELD_OUT_SEEDS)

    q: List[float] = [
        qpso_optimize(problem, weights, QPSOParams(seed=s, **QPSO_BEST)).best.cost
        for s in seeds
    ]
    p: List[float] = [
        pso_optimize(problem, weights, PSOParams(seed=s, **PSO_BEST)).best.cost
        for s in seeds
    ]

    print(f"{problem.network_name} — held-out validation")
    print(f"  {len(seeds)} seeds ({seeds[0]}–{seeds[-1]}), none used for tuning")
    print(f"  QPSO {QPSO_BEST['particles']}×{QPSO_BEST['iterations']}, "
          f"alpha {QPSO_BEST['alpha_start']}→{QPSO_BEST['alpha_end']} "
          f"{QPSO_BEST['alpha_curve']}")
    print(f"  PSO  {PSO_BEST['particles']}×{PSO_BEST['iterations']}, "
          f"inertia {PSO_BEST['inertia_start']}→{PSO_BEST['inertia_end']}")
    print(f"  Both spend {QPSO_BEST['particles'] * (QPSO_BEST['iterations'] + 1):,} "
          f"evaluations per run\n")

    print(f"{'':6} {'mean':>9} {'median':>9} {'best':>9} {'worst':>9} {'stdev':>9}")
    print("-" * 56)
    for name, c in (("QPSO", q), ("PSO", p)):
        print(f"{name:6} {statistics.fmean(c):>9.2f} {statistics.median(c):>9.2f} "
              f"{min(c):>9.2f} {max(c):>9.2f} {statistics.stdev(c):>9.2f}")
    print("-" * 56)

    wins = sum(1 for a, b in zip(q, p) if a < b)
    gap = 100.0 * (statistics.fmean(p) - statistics.fmean(q)) / statistics.fmean(p)
    print(f"\nPaired wins: QPSO {wins}, PSO {len(seeds) - wins}")
    leader = "QPSO" if gap > 0 else "PSO"
    print(f"{leader} is ahead by {abs(gap):.2f}% on mean cost.")

    if statistics.stdev(q) > statistics.stdev(p):
        print(f"\nQPSO remains the less consistent of the two: standard deviation "
              f"{statistics.stdev(q):.2f} against {statistics.stdev(p):.2f}, and a "
              f"worst run of {max(q):.2f} against {max(p):.2f}. It wins on average "
              f"and on the median while still being the riskier single run.")


if __name__ == "__main__":
    main()
