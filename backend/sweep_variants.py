#!/usr/bin/env python3
"""Can QPSO be made to win on the 49-stop instance, honestly?

    python3 sweep_variants.py --runs 8

THE QUESTION

Phase 3 left QPSO 3.25% behind PSO on `ggn-50` with both algorithms tuned over
their own schedules. This asks whether that gap survives three further changes,
two of which are published improvements to QPSO that Phase 3 did not try:

  * SWARM SIZE. 40 particles in 49 dimensions is thin. mbest is an average over
    40 points in 49-space, which is a noisy estimate of anything.
  * WEIGHTED MBEST (Xi, Sun & Xu 2008). Sun's mbest is a plain average, so the
    worst particle sets the jump scale as strongly as the best.
  * ALPHA CURVE. Linear contraction may commit before the swarm has found the
    right region on a large instance.

THE RULE THAT MAKES IT HONEST

Evaluation budget is held CONSTANT at particles x (iterations + 1). Raising the
swarm size lowers the iteration count to match. Without this, "more particles is
better" would just be "more compute is better", which is not a finding.

PSO gets the identical swarm-size treatment over its own inertia schedules. If
QPSO's best beats PSO's best, both were tuned equally hard; if it does not, that
is the answer and it gets reported.
"""

import argparse
import statistics
from typing import List, Optional, Tuple

from app import scenarios
from app.optimizer.fitness import Weights
from app.optimizer.problem import Problem
from app.optimizer.pso import PSOParams
from app.optimizer.pso import optimize as pso_optimize
from app.optimizer.qpso import QPSOParams
from app.optimizer.qpso import optimize as qpso_optimize

BUDGET = 40 * 1001          # what Phase 3 spent per run; every config matches it
SWARMS = [20, 40, 60, 80, 120]
QPSO_ALPHAS = [(0.9, 0.4), (0.7, 0.35), (0.5, 0.25)]
PSO_INERTIAS = [(0.9, 0.4), (0.729, 0.729), (0.5, 0.2), (0.3, 0.1)]


def iterations_for(particles: int) -> int:
    """Iterations that keep the evaluation budget fixed."""
    return max(1, BUDGET // particles - 1)


def run_qpso(problem, weights, seeds, particles, alpha, weighted, curve) -> float:
    iters = iterations_for(particles)
    return statistics.fmean([
        qpso_optimize(
            problem, weights,
            QPSOParams(particles=particles, iterations=iters, seed=s,
                       alpha_start=alpha[0], alpha_end=alpha[1],
                       weighted_mbest=weighted, alpha_curve=curve),
        ).best.cost
        for s in seeds
    ])


def run_pso(problem, weights, seeds, particles, inertia) -> float:
    iters = iterations_for(particles)
    return statistics.fmean([
        pso_optimize(
            problem, weights,
            PSOParams(particles=particles, iterations=iters, seed=s,
                      inertia_start=inertia[0], inertia_end=inertia[1]),
        ).best.cost
        for s in seeds
    ])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--network", default="ggn-50", choices=sorted(scenarios.NETWORKS))
    ap.add_argument("--runs", type=int, default=8)
    args = ap.parse_args()

    problem = Problem(scenarios.get_graph(args.network))
    weights = Weights()
    seeds = list(range(1, args.runs + 1))

    print(f"{problem.network_name} — {len(seeds)} seeds — budget fixed at "
          f"{BUDGET:,} evaluations per run\n")

    # ---- QPSO ---------------------------------------------------------------
    print("QPSO")
    print(f"  {'particles':>9} {'iters':>6} {'alpha':>12} {'mbest':>9} {'curve':>10} {'mean':>10}")
    best_q: Optional[Tuple] = None
    results_q: List[Tuple] = []
    for particles in SWARMS:
        for alpha in QPSO_ALPHAS:
            for weighted in (False, True):
                for curve in ("linear", "quadratic"):
                    m = run_qpso(problem, weights, seeds, particles, alpha, weighted, curve)
                    cfg = (particles, alpha, weighted, curve)
                    results_q.append((cfg, m))
                    if best_q is None or m < best_q[1]:
                        best_q = (cfg, m)
                    print(f"  {particles:>9} {iterations_for(particles):>6} "
                          f"{alpha[0]:.2f}->{alpha[1]:.2f}  "
                          f"{'weighted' if weighted else 'plain':>9} {curve:>10} {m:>10.2f}",
                          flush=True)

    # ---- PSO ----------------------------------------------------------------
    print("\nPSO")
    print(f"  {'particles':>9} {'iters':>6} {'inertia':>14} {'mean':>10}")
    best_p: Optional[Tuple] = None
    for particles in SWARMS:
        for inertia in PSO_INERTIAS:
            m = run_pso(problem, weights, seeds, particles, inertia)
            if best_p is None or m < best_p[1]:
                best_p = ((particles, inertia), m)
            print(f"  {particles:>9} {iterations_for(particles):>6} "
                  f"{inertia[0]:.3f}->{inertia[1]:.3f} {m:>10.2f}", flush=True)

    # ---- verdict ------------------------------------------------------------
    (qp, qa, qw, qc), qm = best_q
    (pp, pi), pm = best_p
    print(f"\nBest QPSO: {qp} particles, alpha {qa[0]}->{qa[1]}, "
          f"{'weighted' if qw else 'plain'} mbest, {qc} curve   mean {qm:.2f}")
    print(f"Best PSO:  {pp} particles, inertia {pi[0]}->{pi[1]}   mean {pm:.2f}")

    gap = 100.0 * (pm - qm) / pm
    if abs(gap) < 0.005:
        print("\nNo separation at each algorithm's best.")
    elif gap > 0:
        print(f"\nQPSO is {gap:.2f}% ahead at each algorithm's best.")
    else:
        print(f"\nPSO is {-gap:.2f}% ahead at each algorithm's best.")

    # What each individual change was worth, holding the rest at Phase 3's setup.
    base = next(m for cfg, m in results_q if cfg == (40, (0.7, 0.35), False, "linear"))
    print(f"\nAgainst the Phase 3 configuration (40 particles, 0.7->0.35, plain, "
          f"linear) at {base:.2f}:")
    for label, cfg in (
        ("weighted mbest alone", (40, (0.7, 0.35), True, "linear")),
        ("quadratic alpha alone", (40, (0.7, 0.35), False, "quadratic")),
        # Labelled by what the sweep actually chose, not by what was expected:
        # the winning swarm turned out to be SMALLER than Phase 3's 40, not
        # bigger. Calling this "bigger swarm" would have reported the hypothesis
        # instead of the result.
        (f"best swarm size ({best_q[0][0]}) alone",
         (best_q[0][0], (0.7, 0.35), False, "linear")),
    ):
        m = next((m for c, m in results_q if c == cfg), None)
        if m is not None:
            delta = 100.0 * (base - m) / base
            verb = "better" if delta > 0 else "worse"
            print(f"  {label:<24} {m:>9.2f}  ({abs(delta):.2f}% {verb})")


if __name__ == "__main__":
    main()
