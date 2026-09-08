"""Quantum-behaved Particle Swarm Optimization.

Sun, Feng and Xu, "Particle swarm optimization with particles having quantum
behavior", CEC 2004. This file is the whole of that algorithm, applied to the
route encoding in `encoding.py` and scored by `fitness.py`.

-------------------------------------------------------------------------------
WHERE IT COMES FROM

Classical PSO (Kennedy and Eberhart, 1995) models a flock. Each particle is a
candidate solution with a position and a VELOCITY, and each step it is pulled
partly toward the best place it has personally found and partly toward the best
place anyone has found. It works, and it has a known failure: velocity is
momentum, momentum shrinks as the swarm agrees, and a swarm that agrees early
agrees forever. It converges on the first decent answer it finds and cannot
leave. That is premature convergence.

QPSO removes velocity entirely.

The physical idea: in classical mechanics a particle has a definite position and
a definite momentum, and knowing both lets you say exactly where it goes next.
In quantum mechanics it has neither. It has a probability cloud, and where it
turns up next is a draw from that cloud - and the cloud has tails, so it can
turn up somewhere far away. Sun's model puts each particle in a delta potential
well centred on the point it is attracted to. Solving the Schrodinger equation
for that well gives an exponential distribution of positions around the centre,
and sampling it is one line of arithmetic.

The consequence that matters for this project: a QPSO particle can jump right
across the search space at any iteration, however converged the swarm is. There
is no momentum to run out of, so there is no state the swarm can get stuck in.
That is the specific reason this algorithm was chosen for a problem whose
landscape is full of local optima.

WHAT "QUANTUM-INSPIRED" HONESTLY MEANS HERE

No quantum hardware, no qubits, no superposition being simulated. The quantum
mechanics supplies the SHAPE OF ONE PROBABILITY DISTRIBUTION and nothing else.
Everything below runs on an ordinary CPU in ordinary floating point. Saying so
plainly is the correct answer when a judge asks, and it is also what the problem
statement means by "quantum-inspired".

-------------------------------------------------------------------------------
THE THREE EQUATIONS

1. MEAN BEST POSITION - where the swarm collectively is

       mbest(t) = (1/N) * SUM over i of P_i(t)

   The average of every particle's personal best, taken component by component.
   Not the best position: the average of the bests. It is the swarm's centre of
   gravity, and it sets the SCALE of the jumps. When the particles have spread
   out and disagree, |mbest - x| is large and jumps are long. As they converge on
   the same region it shrinks and jumps get short. The algorithm goes from
   exploring to refining on its own, driven by the swarm's own spread, with
   nothing scheduling it. Classical PSO has no equivalent - every particle there
   sees only itself and the global best.

2. LOCAL ATTRACTOR - the point this particle is pulled toward

       p_i(t) = phi * P_i(t) + (1 - phi) * G(t)

       where phi = c1*r1 / (c1*r1 + c2*r2),  r1 and r2 fresh uniform randoms

   A random blend of MY best and THE swarm's best. phi lands somewhere in [0, 1]
   afresh for every particle and every dimension, so the attractor sits somewhere
   on the line between the two, at a spot that moves each time. c1 and c2 tilt
   it: raising c1 favours a particle's own experience (more independent search),
   raising c2 favours the global best (faster agreement). Equal values, the
   default, means neither is privileged.

3. POSITION UPDATE - where it actually lands

       x_i(t+1) = p_i(t) +/- alpha * |mbest(t) - x_i(t)| * ln(1/u)

       where u is uniform on (0, 1), and the sign is a fair coin

   This is the sampled draw from the potential well. Read it in pieces:

     p_i             centre the cloud on the attractor
     |mbest - x_i|   size it by how far this particle is from the swarm's centre
     ln(1/u)         the exponential shape, from solving the well
     alpha           a global dial on the whole width
     +/-             either side of the centre, equally likely

   ln(1/u) is where the long jumps live. u is uniform, so ln(1/u) is usually
   small - about 0.69 at the median - but as u approaches 0 it grows without
   bound. Most steps are modest; occasionally one is enormous. That heavy tail IS
   the escape mechanism. It never switches off, at any iteration.

ALPHA, THE CONTRACTION-EXPANSION COEFFICIENT

The one parameter QPSO adds, and the only tuning knob that really matters. It
scales every jump. Sun's recommendation, used here, is to decrease it linearly:

       alpha(k) = alpha_start + (alpha_end - alpha_start) * k / (M - 1)

Default 1.0 down to 0.5 across the run. Early on jumps are wide and the swarm
covers ground; late on they are half as wide and the swarm polishes what it
found. Above roughly 1.7 the swarm provably diverges and never settles; too low
and it converges before it has looked around. 1.0 -> 0.5 is the well-tested range.

Note this is a SECOND contraction mechanism on top of the one in equation 1.
|mbest - x| shrinks by itself as the swarm agrees; alpha shrinks on a fixed
schedule regardless. Together they give a run that reliably ends in refinement.

-------------------------------------------------------------------------------
"""

import math
import random
import time
from dataclasses import dataclass
from typing import Callable, List, Optional

from .encoding import KEY_MAX, KEY_MIN, clamp, decode
from .fitness import Solution, Weights, cost, evaluate
from .problem import Problem


@dataclass(frozen=True)
class QPSOParams:
    """Everything that decides how the search behaves.

    `seed` is not a detail. Fixing it makes a run reproducible, which is what
    lets the Phase 3 benchmark repeat an experiment and lets a demo give the same
    answer twice in front of judges.
    """

    particles: int = 30
    iterations: int = 300
    alpha_start: float = 1.0
    alpha_end: float = 0.5
    c1: float = 1.0
    c2: float = 1.0
    seed: Optional[int] = None

    # --- variants, both OFF by default ------------------------------------
    # Every default above and below reproduces Sun's 2004 algorithm exactly.
    # These two switch on published improvements to it. They are opt-in so that
    # turning them off returns bit-for-bit the same run as before they existed -
    # which tests/test_regression.py checks on every run.

    weighted_mbest: bool = False
    """Weight each particle's contribution to mbest by how good it is.

    Xi, Sun and Xu (2008), "An improved quantum-behaved particle swarm
    optimization algorithm with weighted mean best position". Sun's original
    mbest is a plain average, so the worst particle in the swarm pulls on the
    jump scale exactly as hard as the best one. In a few dimensions that barely
    matters. In 49, where most particles are far from anything good, it means
    the scale is set largely by noise.

    Ranked best to worst, contributions fall linearly from 1.5 to 0.5.
    """

    alpha_curve: str = "linear"
    """How alpha contracts: "linear" (Sun's) or "quadratic".

    Quadratic holds alpha near its start for longer and then drops away sharply,
    spending more of the budget exploring before it commits. On a large instance
    the linear schedule can contract before the swarm has found the right region
    at all.
    """

    def alpha_at(self, k: int) -> float:
        """Equation 3's alpha at iteration k."""
        if self.iterations <= 1:
            return self.alpha_end
        progress = k / (self.iterations - 1)
        if self.alpha_curve == "quadratic":
            # Same endpoints, held high for longer in between.
            progress = progress * progress
        elif self.alpha_curve != "linear":
            raise ValueError(
                f"alpha_curve must be 'linear' or 'quadratic', not {self.alpha_curve!r}"
            )
        return self.alpha_start + (self.alpha_end - self.alpha_start) * progress


@dataclass
class IterationRecord:
    """One row of the convergence history."""

    iteration: int
    best_cost: float
    mean_cost: float
    alpha: float
    evaluations: int


@dataclass
class OptimizeResult:
    """The outcome of a run: the answer, and the evidence for how it was reached."""

    algorithm: str
    best_keys: List[float]
    best: Solution
    history: List[IterationRecord]
    evaluations: int
    elapsed_s: float
    params: QPSOParams
    weights: Weights
    problem_id: str

    @property
    def initial_cost(self) -> float:
        """Best cost after the random starting swarm, before any searching."""
        return self.history[0].best_cost if self.history else self.best.cost

    @property
    def improvement_pct(self) -> float:
        """How much better the answer got. The headline number in a demo."""
        start = self.initial_cost
        if start <= 0:
            return 0.0
        return 100.0 * (start - self.best.cost) / start


def optimize(
    problem: Problem,
    weights: Weights = Weights(),
    params: QPSOParams = QPSOParams(),
    on_iteration: Optional[Callable[[IterationRecord], None]] = None,
) -> OptimizeResult:
    """Run QPSO on a routing problem.

    `on_iteration`, if given, is called after each iteration. Phase 4 uses it to
    stream live progress to the browser; the command line uses it to print.
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

    # --- Initialise -----------------------------------------------------------
    # Positions uniformly at random across the key box. No clever seeding: a
    # head start given to one algorithm and not the other would make the Phase 3
    # comparison worthless, so both start from nothing but randomness.
    X: List[List[float]] = [
        [rng.uniform(KEY_MIN, KEY_MAX) for _ in range(n)] for _ in range(params.particles)
    ]
    # P is each particle's personal best position, and pcost its cost. At the
    # start, where you are is the best you have ever been.
    P: List[List[float]] = [list(x) for x in X]
    pcost: List[float] = [score(x) for x in X]

    best_i = min(range(params.particles), key=lambda i: pcost[i])
    G: List[float] = list(P[best_i])       # global best position
    gcost: float = pcost[best_i]

    history: List[IterationRecord] = []
    c1, c2 = params.c1, params.c2

    # --- Search ---------------------------------------------------------------
    for k in range(params.iterations):
        alpha = params.alpha_at(k)

        # EQUATION 1: the mean best position, componentwise across the swarm.
        # Recomputed every iteration, because the swarm's spread is what sets
        # the jump scale and that spread changes as particles improve.
        if params.weighted_mbest:
            # Rank best to worst, then weight linearly from 1.5 down to 0.5.
            # Dividing by the sum of the weights rather than by N keeps this a
            # true weighted mean for any weight range.
            # NOT named `weights`: that is the objective-weights parameter of
            # this function, and the scoring closure above captures it. Shadowing
            # it here silently scored every candidate against these rank weights
            # instead of the real objective.
            order = sorted(range(params.particles), key=lambda i: pcost[i])
            if params.particles == 1:
                rank_weights = [1.0]
            else:
                rank_weights = [
                    1.5 - 1.0 * r / (params.particles - 1)
                    for r in range(params.particles)
                ]
            total_w = sum(rank_weights)
            mbest = [
                sum(rank_weights[r] * P[i][j] for r, i in enumerate(order)) / total_w
                for j in range(n)
            ]
        else:
            inv = 1.0 / params.particles
            mbest = [sum(P[i][j] for i in range(params.particles)) * inv for j in range(n)]

        for i in range(params.particles):
            xi, pi = X[i], P[i]
            for j in range(n):
                # EQUATION 2: the local attractor. A fresh random blend of this
                # particle's own best and the swarm's best, drawn per dimension.
                r1, r2 = rng.random(), rng.random()
                denom = c1 * r1 + c2 * r2
                phi = (c1 * r1 / denom) if denom > 0.0 else 0.5
                p = phi * pi[j] + (1.0 - phi) * G[j]

                # EQUATION 3: sample the potential well around that attractor.
                u = rng.random()
                while u <= 0.0:
                    # random() can return exactly 0.0; ln(1/0) is undefined.
                    # Redrawing is correct - clamping would quietly bias the tail
                    # that the whole escape mechanism depends on.
                    u = rng.random()
                spread = alpha * abs(mbest[j] - xi[j]) * math.log(1.0 / u)
                xi[j] = clamp(p + spread if rng.random() < 0.5 else p - spread)

            # Score the new position and update the bests. This is ASYNCHRONOUS:
            # an improvement found by particle 3 is visible to particle 4 in the
            # same iteration, rather than being held back to the next one. It
            # spreads good news faster and is the common implementation choice.
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
            alpha=alpha,
            evaluations=evaluations,
        )
        history.append(record)
        if on_iteration is not None:
            on_iteration(record)

    elapsed = time.perf_counter() - started

    return OptimizeResult(
        algorithm="qpso",
        best_keys=list(G),
        best=evaluate(decode(G, problem), problem, weights),
        history=history,
        evaluations=evaluations,
        elapsed_s=elapsed,
        params=params,
        weights=weights,
        problem_id=problem.network_id,
    )
