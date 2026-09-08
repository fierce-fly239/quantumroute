#!/usr/bin/env python3
"""Parameter sweep - find each algorithm's best settings before comparing them.

    python3 sweep.py --network ggn-50 --runs 10

WHY THIS EXISTS

The first honest benchmark on the 49-stop network had PSO beating QPSO by 12%.
Before reporting that, it has to be established whether QPSO was actually losing
or merely mis-tuned: QPSO's published alpha schedule (1.0 -> 0.5) was recommended
for continuous benchmark functions in a handful of dimensions, and this problem
is 49 dimensions of permutation keys, where a large jump in every dimension at
once does not refine a route order, it destroys it.

Reporting a default-parameter loss as an algorithmic loss would be a real error.
So would tuning QPSO until it wins and leaving PSO at defaults. This sweeps BOTH,
over the same seeds and the same budget, and the benchmark then reports each
algorithm at its own best configuration. That is the comparison worth defending.
"""

import argparse
import statistics
from typing import List, Tuple

from app import scenarios
from app.optimizer.fitness import Weights
from app.optimizer.problem import Problem
from app.optimizer.pso import PSOParams
from app.optimizer.pso import optimize as pso_optimize
from app.optimizer.qpso import QPSOParams
from app.optimizer.qpso import optimize as qpso_optimize

# Alpha schedules to try for QPSO. The first is Sun's published recommendation;
# the rest step downward on the hypothesis that 49 dimensions need smaller jumps.
QPSO_GRID: List[Tuple[float, float]] = [
    (1.00, 0.50), (0.90, 0.40), (0.80, 0.40),
    (0.70, 0.35), (0.60, 0.30), (0.50, 0.25), (0.40, 0.20), (0.30, 0.15),
]

# Inertia schedules for PSO. The first is Shi and Eberhart's recommendation.
# extended below 0.5 because the first sweep's winner sat on the grid edge, which
# means the grid had not yet found PSO's best - stopping there would have
# under-tuned the baseline and quietly biased the comparison toward QPSO.
PSO_GRID: List[Tuple[float, float]] = [
    (0.90, 0.40), (0.80, 0.30), (0.729, 0.729), (0.70, 0.40), (0.60, 0.20),
    (0.50, 0.20), (0.40, 0.10), (0.30, 0.10), (0.20, 0.05), (0.10, 0.00),
]


def mean_cost_qpso(problem, weights, seeds, particles, iterations, a0, a1) -> float:
    costs = [
        qpso_optimize(
            problem, weights,
            QPSOParams(particles=particles, iterations=iterations,
                       alpha_start=a0, alpha_end=a1, seed=s),
        ).best.cost
        for s in seeds
    ]
    return statistics.fmean(costs)


def mean_cost_pso(problem, weights, seeds, particles, iterations, w0, w1) -> float:
    costs = [
        pso_optimize(
            problem, weights,
            PSOParams(particles=particles, iterations=iterations,
                      inertia_start=w0, inertia_end=w1, seed=s),
        ).best.cost
        for s in seeds
    ]
    return statistics.fmean(costs)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--network", default="ggn-50", choices=sorted(scenarios.NETWORKS))
    ap.add_argument("--runs", type=int, default=10)
    ap.add_argument("--particles", type=int, default=40)
    ap.add_argument("--iterations", type=int, default=1000)
    args = ap.parse_args()

    problem = Problem(scenarios.get_graph(args.network))
    weights = Weights()
    seeds = list(range(1, args.runs + 1))

    print(f"{problem.network_name} - {len(seeds)} seeds, "
          f"{args.particles}x{args.iterations}\n")

    print("QPSO - alpha schedule")
    print(f"  {'start':>6} {'end':>6} {'mean cost':>12}")
    qpso_rows = []
    for a0, a1 in QPSO_GRID:
        m = mean_cost_qpso(problem, weights, seeds, args.particles, args.iterations, a0, a1)
        qpso_rows.append(((a0, a1), m))
        print(f"  {a0:>6.2f} {a1:>6.2f} {m:>12.2f}")
    best_q = min(qpso_rows, key=lambda r: r[1])

    print("\nPSO - inertia schedule")
    print(f"  {'start':>6} {'end':>6} {'mean cost':>12}")
    pso_rows = []
    for w0, w1 in PSO_GRID:
        m = mean_cost_pso(problem, weights, seeds, args.particles, args.iterations, w0, w1)
        pso_rows.append(((w0, w1), m))
        print(f"  {w0:>6.3f} {w1:>6.3f} {m:>12.2f}")
    best_p = min(pso_rows, key=lambda r: r[1])

    print(f"\nBest QPSO: alpha {best_q[0][0]} -> {best_q[0][1]}   mean {best_q[1]:.2f}")
    print(f"Best PSO:  inertia {best_p[0][0]} -> {best_p[0][1]}   mean {best_p[1]:.2f}")
    gap = 100.0 * (best_p[1] - best_q[1]) / best_p[1]
    # Below this the two are indistinguishable and reporting a winner - or worse,
    # a "-0.00% ahead" from a negative zero - would be reading noise as a result.
    if abs(gap) < 0.005:
        print("\nAt each algorithm's best settings, there is no separation between them.")
    elif gap > 0:
        print(f"\nAt each algorithm's best settings, QPSO is {gap:.2f}% ahead.")
    else:
        print(f"\nAt each algorithm's best settings, PSO is {-gap:.2f}% ahead.")


if __name__ == "__main__":
    main()
