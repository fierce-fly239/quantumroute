"""Classical PSO, and the fairness guarantees the benchmark rests on.

The important tests here are not "does PSO work" - they are the ones proving
QPSO was not handed an advantage. If any of these fail, the Phase 3 comparison
is worthless and should not be reported.
"""

import random

from app.optimizer.encoding import KEY_MAX, KEY_MIN, decode
from app.optimizer.fitness import Weights, cost
from app.optimizer.problem import Problem
from app.optimizer.pso import PSOParams, V_MAX, optimize, swarm_spread
from app.optimizer.qpso import QPSOParams
from app.optimizer.qpso import optimize as qpso_optimize
from tests.fixtures import square_graph


def _problem() -> Problem:
    return Problem(square_graph())


def test_pso_returns_a_feasible_plan():
    r = optimize(_problem(), params=PSOParams(particles=10, iterations=30, seed=1))
    assert r.best.feasible
    assert r.algorithm == "pso"


def test_pso_visits_every_customer_exactly_once():
    p = _problem()
    r = optimize(p, params=PSOParams(particles=10, iterations=30, seed=2))
    visited = [n for route in r.best.routes for n in route]
    assert sorted(visited) == list(range(1, p.customer_count + 1))


def test_pso_improves_on_its_starting_swarm():
    r = optimize(_problem(), params=PSOParams(particles=15, iterations=60, seed=3))
    assert r.best.cost <= r.initial_cost


def test_same_seed_gives_the_same_answer():
    a = optimize(_problem(), params=PSOParams(particles=10, iterations=25, seed=7))
    b = optimize(_problem(), params=PSOParams(particles=10, iterations=25, seed=7))
    assert a.best.cost == b.best.cost
    assert a.best_keys == b.best_keys


def test_different_seeds_take_different_search_paths():
    """Different seeds must actually search differently.

    Deliberately NOT run on the square fixture: every road there is identical, so
    every plan costs the same and all seeds sit at one value from iteration zero.
    That would make this test pass or fail for reasons unrelated to seeding. A
    real network, where cost varies with the route, is the only place the claim
    means anything.
    """
    from app import scenarios
    p = Problem(scenarios.get_graph("ggn-10"))
    paths = {
        tuple(h.mean_cost for h in
              optimize(p, params=PSOParams(particles=8, iterations=20, seed=s)).history)
        for s in range(1, 8)
    }
    assert len(paths) > 1, "every seed produced an identical search path"


def test_keys_stay_inside_the_box():
    r = optimize(_problem(), params=PSOParams(particles=10, iterations=40, seed=4))
    assert all(KEY_MIN <= k <= KEY_MAX for k in r.best_keys)


def test_inertia_schedule_runs_from_start_to_end():
    p = PSOParams(iterations=100, inertia_start=0.9, inertia_end=0.4)
    assert abs(p.inertia_at(0) - 0.9) < 1e-9
    assert abs(p.inertia_at(99) - 0.4) < 1e-9
    assert p.inertia_at(50) < p.inertia_at(10)


def test_inertia_schedule_handles_a_single_iteration():
    assert PSOParams(iterations=1).inertia_at(0) == PSOParams().inertia_end


def test_velocity_cap_is_within_the_key_range():
    assert 0 < V_MAX <= (KEY_MAX - KEY_MIN)


# --- the fairness guarantees -------------------------------------------------

def test_pso_and_qpso_spend_the_same_evaluation_budget():
    """The benchmark's core claim. Both must pay exactly the same number of cost
    evaluations, or any difference in results is a difference in budget."""
    p = _problem()
    a = qpso_optimize(p, params=QPSOParams(particles=12, iterations=40, seed=5))
    b = optimize(p, params=PSOParams(particles=12, iterations=40, seed=5))
    assert a.evaluations == b.evaluations == 12 * (40 + 1)


def test_pso_and_qpso_start_from_the_identical_swarm():
    """Same seed must mean the same starting positions, so a paired run compares
    two move rules and nothing else."""
    p = _problem()
    n = p.customer_count
    rng = random.Random(11)
    expected = [
        [rng.uniform(KEY_MIN, KEY_MAX) for _ in range(n)] for _ in range(9)
    ]
    expected_best = min(cost(decode(x, p), p) for x in expected)

    a = qpso_optimize(p, params=QPSOParams(particles=9, iterations=1, seed=11))
    b = optimize(p, params=PSOParams(particles=9, iterations=1, seed=11))
    # After one iteration the best can only have improved on the starting best.
    assert a.history[0].best_cost <= expected_best + 1e-9
    assert b.history[0].best_cost <= expected_best + 1e-9


def test_both_algorithms_are_scored_by_the_same_function():
    """The reported cost must be reproducible from the returned keys through the
    shared decode + cost path, for both."""
    p = _problem()
    w = Weights()
    for result in (
        qpso_optimize(p, w, QPSOParams(particles=8, iterations=20, seed=6)),
        optimize(p, w, PSOParams(particles=8, iterations=20, seed=6)),
    ):
        assert abs(cost(decode(result.best_keys, p), p, w) - result.best.cost) < 1e-9


def test_history_length_matches_iterations():
    r = optimize(_problem(), params=PSOParams(particles=6, iterations=17, seed=8))
    assert len(r.history) == 17
    assert r.history[-1].best_cost == r.best.cost


def test_best_cost_never_increases():
    r = optimize(_problem(), params=PSOParams(particles=10, iterations=50, seed=9))
    costs = [h.best_cost for h in r.history]
    assert all(b <= a + 1e-12 for a, b in zip(costs, costs[1:]))


def test_rejects_a_swarm_too_small_to_be_a_swarm():
    try:
        optimize(_problem(), params=PSOParams(particles=1, iterations=5))
    except ValueError:
        return
    raise AssertionError("A single-particle swarm should be rejected.")


def test_rejects_zero_iterations():
    try:
        optimize(_problem(), params=PSOParams(particles=5, iterations=0))
    except ValueError:
        return
    raise AssertionError("Zero iterations should be rejected.")


def test_swarm_spread_is_zero_when_every_particle_agrees():
    assert swarm_spread([[0.5, 0.5], [0.5, 0.5], [0.5, 0.5]]) == 0.0


def test_swarm_spread_grows_as_particles_separate():
    tight = swarm_spread([[0.4, 0.4], [0.6, 0.6]])
    wide = swarm_spread([[0.0, 0.0], [1.0, 1.0]])
    assert wide > tight
