"""The network-to-matrices conversion."""

from app import scenarios
from app.optimizer.problem import Problem
from tests.fixtures import square_graph


def test_depot_is_index_zero():
    # Every other module assumes this. If it ever stops being true, routes get
    # priced from the wrong starting point and nothing else fails loudly.
    p = Problem(square_graph())
    assert p.node_ids[0] == "d0"
    assert p.demand[0] == 0


def test_customers_are_one_to_n():
    p = Problem(square_graph())
    assert p.customer_count == 3
    assert p.size == 4
    assert sorted(p.demand[1:]) == [4, 5, 6]


def test_matrices_are_complete():
    p = Problem(scenarios.get_graph("ggn-10"))
    for i in range(p.size):
        for j in range(p.size):
            assert p.time[i][j] != float("inf")
            assert p.dist[i][j] != float("inf")


def test_diagonal_is_zero():
    p = Problem(scenarios.get_graph("ggn-10"))
    for i in range(p.size):
        assert p.dist[i][i] == 0.0
        assert p.time[i][i] == 0.0


def test_delay_is_the_traffic_part_of_the_time():
    # travel_time = free_flow x congestion, so delay = time - time/congestion.
    # On the fixture every road is 20 minutes at congestion 2.0, so exactly half
    # the journey - 10 minutes - is traffic.
    p = Problem(square_graph())
    assert abs(p.delay[0][1] - 10.0) < 1e-9


def test_roads_are_directed():
    # The traffic model charges more for driving INTO a busy zone than out of it.
    # If this ever came out symmetric, the directed graph the problem statement
    # asks for would have quietly become an undirected one.
    p = Problem(scenarios.get_graph("ggn-10"))
    asymmetric = any(
        abs(p.time[i][j] - p.time[j][i]) > 1e-6
        for i in range(p.size)
        for j in range(p.size)
        if i != j
    )
    assert asymmetric


def test_rejects_network_without_one_depot():
    graph = square_graph()
    graph.nodes[1].type = graph.nodes[0].type  # two depots
    try:
        Problem(graph)
    except ValueError as e:
        assert "depot" in str(e).lower()
    else:
        raise AssertionError("Two depots should have been refused.")


def test_fleet_arithmetic():
    p = Problem(square_graph(vehicles=2, capacity=10))
    assert p.fleet_capacity == 20
    assert p.total_demand == 15
    assert p.min_vehicles_needed == 2  # ceil(15/10)
