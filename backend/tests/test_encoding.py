"""Random-key encoding: the interpreter between numbers and route plans."""

import random

from app import scenarios
from app.optimizer.encoding import decode, encode, route_loads
from app.optimizer.problem import Problem
from tests.fixtures import square_graph, tight_graph


def test_keys_sort_into_visiting_order():
    # Three customers, plenty of capacity, so one van takes all three in key
    # order. Keys [0.9, 0.1, 0.5] means Bravo (0.1), Charlie (0.5), Alpha (0.9),
    # which is node indices 2, 3, 1.
    p = Problem(square_graph(vehicles=3, capacity=100))
    assert decode([0.9, 0.1, 0.5], p) == [[2, 3, 1]]


def test_every_stop_appears_exactly_once():
    p = Problem(scenarios.get_graph("ggn-50"))
    rng = random.Random(0)
    for _ in range(50):
        keys = [rng.random() for _ in range(p.customer_count)]
        visited = [node for route in decode(keys, p) for node in route]
        assert sorted(visited) == list(range(1, p.customer_count + 1))


def test_no_van_is_overloaded():
    # The whole point of enforcing capacity inside the decoder: it cannot be
    # violated by any input, so the search never wastes time on plans that break it.
    p = Problem(scenarios.get_graph("ggn-50"))
    rng = random.Random(1)
    for _ in range(50):
        keys = [rng.random() for _ in range(p.customer_count)]
        routes = decode(keys, p)
        assert all(load <= p.capacity for load in route_loads(routes, p))


def test_any_vector_decodes():
    # The property the encoding was chosen for: there is no such thing as an
    # invalid particle position, so nothing ever needs repairing.
    p = Problem(scenarios.get_graph("ggn-10"))
    n = p.customer_count
    for keys in ([0.0] * n, [1.0] * n, [0.5] * n, list(range(n))):
        routes = decode([float(k) for k in keys], p)
        assert sum(len(r) for r in routes) == n


def test_ties_are_broken_deterministically():
    # Identical keys must not produce a different plan on a different run, or the
    # benchmark stops being repeatable.
    p = Problem(scenarios.get_graph("ggn-10"))
    flat = [0.5] * p.customer_count
    assert decode(flat, p) == decode(flat, p)
    assert decode(flat, p) == [[1, 2, 3, 4], [5, 6], [7, 8, 9]]


def test_encode_decode_round_trip():
    p = Problem(scenarios.get_graph("ggn-10"))
    rng = random.Random(2)
    for _ in range(30):
        keys = [rng.random() for _ in range(p.customer_count)]
        routes = decode(keys, p)
        assert decode(encode(routes, p), p) == routes


def test_wrong_number_of_keys_is_refused():
    p = Problem(scenarios.get_graph("ggn-10"))
    try:
        decode([0.5, 0.5], p)
    except ValueError as e:
        assert "keys" in str(e)
    else:
        raise AssertionError("A short key vector should have been refused.")


def test_decoder_can_need_more_vans_than_the_fleet():
    # Documented behaviour, not an accident: filling vans in visiting order can
    # close one early. Demands 7, 3, 7, 3 into two 10-unit vans fit perfectly if
    # each 7 is paired with a 3 - but visiting the two heavy stops first forces a
    # third van for work two could do. Fitness prices that rather than the
    # decoder quietly hiding it.
    p = Problem(tight_graph())

    good = decode([0.1, 0.2, 0.3, 0.4], p)      # 7, 3, 7, 3
    assert good == [[1, 2], [3, 4]]
    assert len(good) == p.vehicles

    bad = decode([0.1, 0.3, 0.2, 0.4], p)       # 7, 7, 3, 3
    assert bad == [[1], [3, 2], [4]]
    assert len(bad) > p.vehicles
