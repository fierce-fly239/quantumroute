"""Classical Particle Swarm Optimization - the baseline QPSO has to beat.

Kennedy and Eberhart, "Particle swarm optimization", ICNN 1995, with the inertia
weight of Shi and Eberhart, "A modified particle swarm optimizer", CEC 1998.

-------------------------------------------------------------------------------
WHY THIS FILE EXISTS

Objective 3 of SIH26137 asks for QPSO to be compared against classical
metaheuristics. A comparison is only worth reading if the other side was
implemented properly, so this is a real PSO with the standard recommended
parameters - not a strawman built to lose.

If QPSO cannot beat this, that is a finding and we report it. A prepared honest
answer beats a tuned one.

-------------------------------------------------------------------------------
WHAT MAKES THE COMPARISON FAIR

Five things are held identical between this file and `qpso.py`. Every one of
them is a way the benchmark could otherwise have been rigged:

  1. SAME ENCODING. Both search a vector of random keys in [0, 1] and decode it
     through the same `decode()`. Neither algorithm gets a representation that
     suits it better.
  2. SAME OBJECTIVE. Both are scored by the same `cost()` with the same weights.
  3. SAME EVALUATION BUDGET. Both spend exactly particles x (iterations + 1)
     evaluations - one per particle to initialise, one per particle per
     iteration. Cost evaluations, not wall-clock, are the currency: it is the
     unit that does not depend on whose code is written more tightly.
  4. SAME STARTING SWARM. Given the same seed, both start from the identical
     random positions, because both draw them the same way from the same
     generator before doing anything else.
  5. SAME BEST-UPDATE RULE. Both update personal and global bests
     asynchronously, in the same order.

What differs is only the move rule - equations. Which is the thing being tested.

-------------------------------------------------------------------------------
THE ALGORITHM

Every particle carries a position AND a velocity. Each step:

    v(t+1) = w*v(t)  +  c1*r1*(P - x)  +  c2*r2*(G - x)
    x(t+1) = x(t) + v(t+1)

Read the velocity as three pulls added together:

    w*v         MOMENTUM - keep going the way you were going
    c1*r1*(P-x) COGNITIVE - pull back toward my own best
    c2*r2*(G-x) SOCIAL    - pull toward the swarm's best

`w` is the inertia weight, decreasing 0.9 -> 0.4 over the run. High early means
momentum dominates and particles range widely; low late means the two pulls
dominate and particles settle. It is the direct analogue of QPSO's alpha, and it
is scheduled the same way so neither algorithm gets a better-tuned schedule.

`c1 = c2 = 2.0` is Kennedy and Eberhart's original recommendation and remains
the common default.

THE WEAKNESS THIS EXISTS TO DEMONSTRATE

Look at the velocity equation when the swarm has converged. If every particle
sits near G, then (P - x) and (G - x) are both near zero, so the only thing left
is w*v - and w < 1, so each step the velocity is multiplied by a number smaller
than one. It decays geometrically toward zero.

A converged PSO swarm cannot re-expand. There is no term in the equation capable
of producing a large displacement once the differences are small. That is
premature convergence, and it is structural, not a tuning problem.

QPSO's `ln(1/u)` has no such ceiling: it can produce an arbitrarily large jump at
any iteration regardless of how converged the swarm is. That is precisely the
difference the benchmark is built to measure.
"""

import random
import time
from dataclasses import dataclass
from typing import Callable, List, Optional

from .encoding import KEY_MAX, KEY_MIN, clamp, decode
from .fitness import Solution, Weights, cost, evaluate
from .problem import Problem
from .qpso import IterationRecord

# Velocity is capped at half the width of the key box. Without a cap, PSO can
# reach a state where every step overshoots the whole search space and the swarm
# never settles - a well-known failure that says nothing about the algorithm's
# real behaviour. Clamping is standard practice, not a favour.
V_MAX = 0.5 * (KEY_MAX - KEY_MIN)


@dataclass(frozen=True)
class PSOParams:
    """Deliberately the same shape as QPSOParams, so the benchmark can drive both
    through one interface and nobody has to wonder whether the budgets matched."""

    particles: int = 30
    iterations: int = 300
    inertia_start: float = 0.9
    inertia_end: float = 0.4
    c1: float = 2.0
    c2: float = 2.0
    seed: Optional[int] = None

    def inertia_at(self, k: int) -> float:
        """The inertia weight at iteration k, on the same linear schedule shape
        QPSO uses for alpha."""
        if self.iterations <= 1:
            return self.inertia_end
        progress = k / (self.iterations - 1)
        return self.inertia_start + (self.inertia_end - self.inertia_start) * progress


@dataclass
class PSOResult:
    """Same fields as QPSO's OptimizeResult. The benchmark treats them alike."""

    algorithm: str
    best_keys: List[float]
    best: Solution
    history: List[IterationRecord]
    evaluations: int
    elapsed_s: float
    params: PSOParams
    weights: Weights
    problem_id: str

    @property
    def initial_cost(self) -> float:
        return self.history[0].best_cost if self.history else self.best.cost

    @property
    def improvement_pct(self) -> float:
        start = self.initial_cost
        if start <= 0:
            return 0.0
        return 100.0 * (start - self.best.cost) / start


def optimize(
    problem: Problem,
    weights: Weights = Weights(),
    params: PSOParams = PSOParams(),
    on_iteration: Optional[Callable[[IterationRecord], None]] = None,
) -> PSOResult:
    """Run classical PSO on a routing problem.

    Structurally identical to `qpso.optimize` on purpose: same initialisation,
    same loop shape, same bookkeeping, same asynchronous best updates. Only the
    move rule differs. Reading the two side by side should make it obvious that
    nothing else was changed.
    """
    if params.particles < 2:
        raise ValueError("A swarm needs at least 2 particles.")
    if params.iterations < 1:
        raise ValueError("A run needs at least 1 iteration.")

    rng = random.Random(params.seed)
    n = problem.customer_count
    started = time.perf_counter()
    evaluations = 0

    def score(keys: List[float]) -> float:
        nonlocal evaluations
        evaluations += 1
        return cost(decode(keys, problem), problem, weights)

    # Identical initialisation to QPSO: same draw order from the same seeded
    # generator, so with a given seed both algorithms begin from the same swarm.
    X: List[List[float]] = [
        [rng.uniform(KEY_MIN, KEY_MAX) for _ in range(n)] for _ in range(params.particles)
    ]
    # Velocities start at zero. The alternative - small random velocities - would
    # give PSO a nudge QPSO has no equivalent of on iteration one.
    V: List[List[float]] = [[0.0] * n for _ in range(params.particles)]

    P: List[List[float]] = [list(x) for x in X]
    pcost: List[float] = [score(x) for x in X]

    best_i = min(range(params.particles), key=lambda i: pcost[i])
    G: List[float] = list(P[best_i])
    gcost: float = pcost[best_i]

    history: List[IterationRecord] = []
    c1, c2 = params.c1, params.c2

    for k in range(params.iterations):
        w = params.inertia_at(k)

        for i in range(params.particles):
            xi, vi, pi = X[i], V[i], P[i]
            for j in range(n):
                r1, r2 = rng.random(), rng.random()
                # The velocity update: momentum + cognitive pull + social pull.
                v = w * vi[j] + c1 * r1 * (pi[j] - xi[j]) + c2 * r2 * (G[j] - xi[j])
                if v > V_MAX:
                    v = V_MAX
                elif v < -V_MAX:
                    v = -V_MAX
                vi[j] = v
                xi[j] = clamp(xi[j] + v)

            c = score(xi)
            if c < pcost[i]:
                P[i] = list(xi)
                pcost[i] = c
                if c < gcost:
                    G = list(xi)
                    gcost = c

        record = IterationRecord(
            iteration=k,
            best_cost=gcost,
            mean_cost=sum(pcost) / params.particles,
            alpha=w,          # the inertia weight, stored in the same slot alpha uses
            evaluations=evaluations,
        )
        history.append(record)
        if on_iteration is not None:
            on_iteration(record)

    return PSOResult(
        algorithm="pso",
        best_keys=list(G),
        best=evaluate(decode(G, problem), problem, weights),
        history=history,
        evaluations=evaluations,
        elapsed_s=time.perf_counter() - started,
        params=params,
        weights=weights,
        problem_id=problem.network_id,
    )


def swarm_spread(positions: List[List[float]]) -> float:
    """Mean distance of particles from their own centre.

    Not used by the search. It is here because "the swarm collapsed" is the
    central claim about PSO's weakness, and a claim like that should be
    measurable rather than asserted.
    """
    if not positions:
        return 0.0
    n = len(positions[0])
    centre = [sum(p[j] for p in positions) / len(positions) for j in range(n)]
    total = 0.0
    for p in positions:
        total += sum(abs(p[j] - centre[j]) for j in range(n)) / n
    return total / len(positions)
