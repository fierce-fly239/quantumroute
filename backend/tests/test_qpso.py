"""QPSO itself: the three equations, and the guarantees a benchmark depends on."""

from app import scenarios
from app.optimizer.encoding import KEY_MAX, KEY_MIN
from app.optimizer.problem import Problem
from app.optimizer.qpso import QPSOParams, optimize

FAST = QPSOParams(particles=20, iterations=80, seed=42)


def _ggn10() -> Problem:
    return Problem(scenarios.get_graph("ggn-10"))


def test_same_seed_gives_an_identical_run():
    # The single most important property in this file. Phase 3 compares QPSO
    # against PSO by repeating runs; if a run cannot be repeated there is nothing
    # to compare, and a demo that gives a different answer each time is not a demo.
    a = optimize(_ggn10(), params=FAST)
    b = optimize(_ggn10(), params=FAST)
    assert a.best.cost == b.best.cost
    assert a.best_keys == b.best_keys
    assert [r.best_cost for r in a.history] == [r.best_cost for r in b.history]


def test_different_seeds_explore_differently():
    a = optimize(_ggn10(), params=QPSOParams(particles=20, iterations=80, seed=1))
    b = optimize(_ggn10(), params=QPSOParams(particles=20, iterations=80, seed=2))
    assert a.best_keys != b.best_keys


def test_the_answer_is_never_worse_than_where_it_started():
    # The global best only ever moves when something beats it, so the curve can
    # never go up. If it did, a better solution had been found and then lost.
    r = optimize(_ggn10(), params=FAST)
    costs = [rec.best_cost for rec in r.history]
    assert all(b <= a + 1e-12 for a, b in zip(costs, costs[1:]))
    assert r.best.cost <= r.initial_cost


def test_it_actually_improves():
    r = optimize(_ggn10(), params=FAST)
    assert r.best.cost < r.initial_cost
    assert r.improvement_pct > 0


def test_alpha_runs_from_start_to_end():
    # Equation 3's contraction-expansion coefficient, on its linear schedule.
    p = QPSOParams(particles=10, iterations=100, alpha_start=1.0, alpha_end=0.5)
    assert abs(p.alpha_at(0) - 1.0) < 1e-12
    assert abs(p.alpha_at(99) - 0.5) < 1e-12
    assert abs(p.alpha_at(49) - 0.7525) < 1e-4  # halfway, near enough
    r = optimize(_ggn10(), params=QPSOParams(particles=10, iterations=20, seed=3))
    assert abs(r.history[0].alpha - 1.0) < 1e-12
    assert abs(r.history[-1].alpha - 0.5) < 1e-12


def test_evaluation_budget_is_exactly_what_it_claims():
    # Phase 3 gives QPSO and PSO the same number of fitness evaluations, so that
    # number has to be predictable: one per particle to set up, then one per
    # particle per iteration.
    params = QPSOParams(particles=15, iterations=40, seed=5)
    r = optimize(_ggn10(), params=params)
    assert r.evaluations == 15 * (40 + 1)
    assert len(r.history) == 40


def test_positions_stay_inside_the_key_box():
    r = optimize(_ggn10(), params=FAST)
    assert all(KEY_MIN <= k <= KEY_MAX for k in r.best_keys)


def test_the_answer_is_a_legal_delivery_plan():
    r = optimize(_ggn10(), params=QPSOParams(particles=30, iterations=200, seed=11))
    assert r.best.feasible
    assert r.best.vehicles_used <= 3  # the ggn-10 fleet
    visited = sorted(n for route in r.best.routes for n in route)
    assert visited == list(range(1, 10))


def test_the_progress_callback_fires_once_per_iteration():
    seen = []
    optimize(_ggn10(), params=QPSOParams(particles=10, iterations=25, seed=6),
             on_iteration=seen.append)
    assert [rec.iteration for rec in seen] == list(range(25))


def test_nonsense_parameters_are_refused():
    for bad in (QPSOParams(particles=1), QPSOParams(iterations=0)):
        try:
            optimize(_ggn10(), params=bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"{bad} should have been refused.")


def test_a_bigger_budget_does_not_do_worse():
    # Not a guarantee for any single seed - it is a stochastic search - but
    # averaged over several seeds more searching should not hurt.
    def mean_cost(iterations: int) -> float:
        costs = [
            optimize(_ggn10(), params=QPSOParams(particles=20, iterations=iterations, seed=s)).best.cost
            for s in range(5)
        ]
        return sum(costs) / len(costs)

    assert mean_cost(300) <= mean_cost(30)


# --- the opt-in variants -----------------------------------------------------
# Added with the variants themselves, after the first implementation named its
# rank-weight list `weights` and so shadowed the objective-weights parameter the
# scoring closure captures. Every candidate was then scored against the rank
# weights. Nothing else caught it: the defaults were untouched, so the golden
# regression values still passed.

def test_every_variant_combination_produces_a_legal_plan():
    p = _ggn10()
    for weighted in (False, True):
        for curve in ("linear", "quadratic"):
            r = optimize(p, params=QPSOParams(
                particles=10, iterations=30, seed=3,
                weighted_mbest=weighted, alpha_curve=curve))
            visited = sorted(n for route in r.best.routes for n in route)
            assert visited == list(range(1, p.customer_count + 1))
            assert r.best.feasible


def test_variants_are_scored_by_the_real_objective():
    """The reported cost must be reproducible from the returned keys through the
    shared decode + cost path. This is what the shadowing bug broke."""
    from app.optimizer.encoding import decode
    from app.optimizer.fitness import Weights, cost
    p = _ggn10()
    w = Weights(time=2.0, distance=1.0, congestion=0.5, vehicle=20.0)
    for weighted in (False, True):
        r = optimize(p, w, QPSOParams(particles=10, iterations=25, seed=4,
                                      weighted_mbest=weighted))
        assert abs(cost(decode(r.best_keys, p), p, w) - r.best.cost) < 1e-9


def test_weighted_mbest_changes_the_search():
    """If turning it on changed nothing, it is not wired up."""
    p = _ggn10()
    plain = optimize(p, params=QPSOParams(particles=12, iterations=40, seed=5,
                                          weighted_mbest=False))
    weighted = optimize(p, params=QPSOParams(particles=12, iterations=40, seed=5,
                                             weighted_mbest=True))
    assert [h.mean_cost for h in plain.history] != [h.mean_cost for h in weighted.history]


def test_quadratic_alpha_has_the_same_endpoints_but_holds_higher():
    linear = QPSOParams(iterations=100, alpha_start=1.0, alpha_end=0.5)
    quad = QPSOParams(iterations=100, alpha_start=1.0, alpha_end=0.5,
                      alpha_curve="quadratic")
    assert abs(quad.alpha_at(0) - linear.alpha_at(0)) < 1e-9
    assert abs(quad.alpha_at(99) - linear.alpha_at(99)) < 1e-9
    # Held nearer the start value in between - that is the whole point of it.
    assert quad.alpha_at(50) > linear.alpha_at(50)


def test_an_unknown_alpha_curve_is_refused():
    try:
        QPSOParams(iterations=10, alpha_curve="sigmoid").alpha_at(1)
    except ValueError:
        return
    raise AssertionError("An unrecognised alpha_curve should be rejected, not ignored.")


def test_weighted_mbest_handles_a_two_particle_swarm():
    """The rank weights divide by (particles - 1); the smallest legal swarm is
    the edge case that would hit a division by zero if it were miscoded."""
    r = optimize(_ggn10(), params=QPSOParams(particles=2, iterations=10, seed=6,
                                               weighted_mbest=True))
    assert r.best.feasible
