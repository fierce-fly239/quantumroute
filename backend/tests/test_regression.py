"""Golden values: what the solvers produce today, locked in.

WHY

Every other test here checks a property - the plan is feasible, the budget is
what it claims, the cost never rises. All of those would still pass if a change
quietly made the search WORSE, as long as it stayed feasible and legal.

These do not. They pin the exact number each algorithm returns for a fixed seed
on a fixed network. Any edit that changes the search - a different attractor, a
reordered random draw, an extra rng call slipped into a loop - changes these
numbers and fails here immediately, with the diff pointing at what moved.

Captured 2026-09-06, after Phase 4, with everything verified working.

IF ONE OF THESE FAILS

It does not automatically mean the change is wrong. It means the change altered
results, which must then be a deliberate decision rather than a surprise:

  * Improved the search on purpose? Re-capture the values and say so in the
    changelog, with the before and after.
  * Did not expect any change? Something moved that should not have. Find it
    before going further.

Never "fix" a failure here by loosening the tolerance.
"""

from app import scenarios
from app.optimizer.exact import exact_optimum
from app.optimizer.problem import Problem
from app.optimizer.pso import PSOParams
from app.optimizer.pso import optimize as pso_optimize
from app.optimizer.qpso import QPSOParams
from app.optimizer.qpso import optimize as qpso_optimize

# Floats are reproducible here because every operation runs in the same order on
# the same seeded generator. The tolerance absorbs nothing but the last bit.
TOL = 1e-6

# network, iterations, seed, expected QPSO cost, expected PSO cost
GOLDEN = [
    ("ggn-10", 500, 1, 183.090831, 183.090831),
    ("ggn-10", 500, 42, 182.660424, 180.707934),
    ("ggn-50", 1000, 1, 1408.642786, 1256.762601),
    ("ggn-50", 1000, 42, 1561.727985, 1386.340956),
]

# The tuned schedules from the Phase 3 sweep. These are part of the golden
# values: changing a default schedule changes every number above.
ALPHA = (0.9, 0.4)
INERTIA = (0.729, 0.729)

EXACT_GGN10 = 180.707934


def _problem(net: str) -> Problem:
    return Problem(scenarios.get_graph(net))


def test_qpso_golden_costs():
    for net, iters, seed, expected, _ in GOLDEN:
        got = qpso_optimize(
            _problem(net),
            params=QPSOParams(particles=40, iterations=iters, seed=seed,
                              alpha_start=ALPHA[0], alpha_end=ALPHA[1]),
        ).best.cost
        assert abs(got - expected) < TOL, (
            f"QPSO on {net} seed {seed}: expected {expected}, got {got:.6f}. "
            f"The search changed. See this file's docstring."
        )


def test_pso_golden_costs():
    for net, iters, seed, _, expected in GOLDEN:
        got = pso_optimize(
            _problem(net),
            params=PSOParams(particles=40, iterations=iters, seed=seed,
                             inertia_start=INERTIA[0], inertia_end=INERTIA[1]),
        ).best.cost
        assert abs(got - expected) < TOL, (
            f"PSO on {net} seed {seed}: expected {expected}, got {got:.6f}. "
            f"The search changed. See this file's docstring."
        )


def test_exact_optimum_is_unchanged():
    """The proven optimum depends only on the network and the weights, not on any
    search. If this moves, the PROBLEM changed - a coordinate, a demand, a
    congestion figure - and every benchmark number in the KB is now stale."""
    got = exact_optimum(_problem("ggn-10")).cost
    assert abs(got - EXACT_GGN10) < TOL, (
        f"The proven optimum for ggn-10 moved: expected {EXACT_GGN10}, got {got:.6f}. "
        f"The network or the objective changed, not the search."
    )


def test_default_schedules_are_still_the_tuned_ones():
    """The golden costs above assume these defaults. If someone changes a default
    schedule, the numbers move and it should be obvious why."""
    assert (QPSOParams().alpha_start, QPSOParams().alpha_end) == (1.0, 0.5), (
        "QPSOParams still carries Sun's published default; the tuned schedule is "
        "applied by the callers (solve.py, bench.py, the API). If that changed, "
        "the golden values need re-capturing."
    )
    assert (PSOParams().inertia_start, PSOParams().inertia_end) == (0.9, 0.4)
