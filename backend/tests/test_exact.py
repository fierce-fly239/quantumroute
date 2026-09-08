"""The exact solver, and what it proves about QPSO.

The point of these tests is not that the DP is fast. It is that the DP is RIGHT,
because everything the project claims about solution quality is measured against
it. A verifier nobody has verified is worth nothing.
"""

from itertools import permutations

from app import scenarios
from app.optimizer.exact import TooLargeForExact, exact_optimum, subsets_required
from app.optimizer.fitness import evaluate
from app.optimizer.problem import Problem
from app.optimizer.qpso import QPSOParams, optimize
from tests.fixtures import square_graph, tight_graph


def _brute_force(problem: Problem) -> float:
    """Independent check: try every assignment of stops to vans and every order
    within each van. Hopelessly slow, obviously correct, and small enough here.

    Written deliberately differently from the DP - no subsets, no memoisation,
    no shared code beyond `evaluate` - so that agreement between them means
    something rather than meaning both share a bug.
    """
    n = problem.customer_count
    v = problem.vehicles
    best = float("inf")

    for assignment in _assignments(n, v):
        vans = [[] for _ in range(v)]
        for customer, van in enumerate(assignment):
            vans[van].append(customer + 1)
        if any(sum(problem.demand[c] for c in van) > problem.capacity for van in vans):
            continue
        for ordered in _orderings(vans):
            routes = [van for van in ordered if van]
            best = min(best, evaluate(routes, problem).cost)
    return best


def _assignments(n: int, v: int):
    if n == 0:
        yield []
        return
    for rest in _assignments(n - 1, v):
        for van in range(v):
            yield rest + [van]


def _orderings(vans):
    if not vans:
        yield []
        return
    for head in permutations(vans[0]):
        for tail in _orderings(vans[1:]):
            yield [list(head)] + tail


def test_dp_agrees_with_brute_force_on_the_square():
    p = Problem(square_graph(vehicles=2, capacity=10))
    assert abs(exact_optimum(p).cost - _brute_force(p)) < 1e-9


def test_dp_agrees_with_brute_force_on_the_tight_fleet():
    p = Problem(tight_graph())
    assert abs(exact_optimum(p).cost - _brute_force(p)) < 1e-9


def test_the_optimum_is_a_complete_legal_plan():
    p = Problem(scenarios.get_graph("ggn-10"))
    s = exact_optimum(p)
    assert s.feasible
    assert sorted(n for route in s.routes for n in route) == list(range(1, 10))


def test_nothing_beats_the_optimum():
    # If any random plan came in cheaper than the "optimum", the DP is wrong.
    import random

    from app.optimizer.encoding import decode

    p = Problem(scenarios.get_graph("ggn-10"))
    floor = exact_optimum(p).cost
    rng = random.Random(0)
    for _ in range(300):
        keys = [rng.random() for _ in range(p.customer_count)]
        assert evaluate(decode(keys, p), p).cost >= floor - 1e-9


def test_qpso_gets_close_to_the_proven_optimum():
    # The headline claim of Phase 2, asserted rather than asserted-in-a-slide.
    p = Problem(scenarios.get_graph("ggn-10"))
    floor = exact_optimum(p).cost
    r = optimize(p, params=QPSOParams(particles=40, iterations=500, seed=7))
    gap = (r.best.cost - floor) / floor
    assert gap < 0.05, f"QPSO came in {gap:.1%} above the optimum"


def test_the_big_instance_is_refused_and_says_why():
    p = Problem(scenarios.get_graph("ggn-50"))
    assert subsets_required(p) == 2 ** 49
    try:
        exact_optimum(p)
    except TooLargeForExact as e:
        assert "2^49" in str(e)
    else:
        raise AssertionError("A 49-stop instance cannot be solved exactly.")
