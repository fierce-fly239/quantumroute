"""The cost function. Every expected number here is worked out by hand.

The square fixture makes that possible: every road is 10 km, 20 minutes, and
congestion 2.0, so half of every journey's 20 minutes - 10 of them - is traffic
delay. A van serving k stops drives k+1 road segments, out and back included.

Default weights: time 1.0, distance 0.5, congestion 0.3, vehicle 15.0.
"""

from app.optimizer.fitness import Weights, cost, evaluate
from app.optimizer.problem import Problem
from tests.fixtures import square_graph


def test_one_van_serving_three_stops():
    # 4 segments: depot -> 1 -> 2 -> 3 -> depot.
    #   distance 40 km, time 80 min, delay 40 min, 1 van
    #   cost = 1.0*80 + 0.5*40 + 0.3*40 + 15.0*1 = 80 + 20 + 12 + 15 = 127
    p = Problem(square_graph(vehicles=3, capacity=100))
    s = evaluate([[1, 2, 3]], p)
    assert s.total_distance_km == 40.0
    assert s.total_time_min == 80.0
    assert s.congestion_delay_min == 40.0
    assert s.vehicles_used == 1
    assert abs(s.cost - 127.0) < 1e-9


def test_the_return_leg_is_charged():
    # A single stop is 2 segments, not 1. A van that does not come home is not a
    # delivery van, and forgetting the return leg is the classic VRP off-by-one.
    p = Problem(square_graph(vehicles=3, capacity=100))
    s = evaluate([[1]], p)
    assert s.total_distance_km == 20.0


def test_splitting_across_vans_costs_more():
    # 5 segments instead of 4, plus a second van:
    #   cost = 100 + 25 + 15 + 30 = 170
    p = Problem(square_graph(vehicles=3, capacity=100))
    s = evaluate([[1], [2, 3]], p)
    assert s.vehicles_used == 2
    assert abs(s.cost - 170.0) < 1e-9


def test_congestion_share_reads_correctly():
    # Congestion 2.0 everywhere means exactly half of all driving time is traffic.
    p = Problem(square_graph(vehicles=3, capacity=100))
    s = evaluate([[1, 2, 3]], p)
    assert abs(s.congestion_share - 0.5) < 1e-9


def test_overflow_is_priced_out_of_reach():
    # One van in the fleet, three used. Two vans over, at 5000 each. The penalty
    # has to dwarf any routing gain or the search would learn to buy extra vans
    # to shorten routes.
    p = Problem(square_graph(vehicles=1, capacity=100))
    s = evaluate([[1], [2], [3]], p)
    assert s.vehicles_used == 3
    assert s.overflow_vehicles == 2
    assert not s.feasible
    assert abs(s.cost - (213.0 + 10000.0)) < 1e-9


def test_overloaded_van_is_caught():
    p = Problem(square_graph(vehicles=3, capacity=5))
    s = evaluate([[1]], p)  # Alpha demands 6 into a 5-unit van
    assert s.overloaded_routes == 1
    assert not s.feasible


def test_a_legal_plan_is_feasible():
    p = Problem(square_graph(vehicles=2, capacity=10))
    s = evaluate([[1, 3], [2]], p)  # loads 10 and 5
    assert s.feasible
    assert s.overflow_vehicles == 0
    assert s.overloaded_routes == 0


def test_cost_matches_evaluate():
    # `cost` is the fast path used in the search loop and `evaluate` is the
    # reporting path. If they ever disagreed, the swarm would be optimising one
    # thing and the demo would be showing another.
    p = Problem(square_graph(vehicles=2, capacity=10))
    for routes in ([[1, 3], [2]], [[1], [2], [3]], [[2, 3], [1]]):
        assert abs(cost(routes, p) - evaluate(routes, p).cost) < 1e-9


def test_weights_actually_change_the_answer():
    # With congestion weighted at zero the delay term stops contributing:
    #   127 - 0.3*40 = 115
    p = Problem(square_graph(vehicles=3, capacity=100))
    s = evaluate([[1, 2, 3]], p, Weights(congestion=0.0))
    assert abs(s.cost - 115.0) < 1e-9


def test_empty_routes_are_ignored():
    p = Problem(square_graph(vehicles=3, capacity=100))
    assert evaluate([[1, 2, 3], []], p).vehicles_used == 1
