"""TomTom provider, tested without the network.

The response below was recorded from a real Matrix v2 call on 16 Sep 2026 (two
Gurugram origins, three destinations, live traffic). Everything here exercises
the pure conversion and the snapshot round-trip; nothing talks to TomTom.
"""

import json

from app import config, tomtom, traffic
from app.models import Node, NodeType, Zone
from app.optimizer.problem import Problem
from tests.fixtures import square_graph

RECORDED = {
    "data": [
        {"originIndex": 0, "destinationIndex": 0, "routeSummary": {
            "lengthInMeters": 0, "travelTimeInSeconds": 0, "trafficDelayInSeconds": 0}},
        {"originIndex": 0, "destinationIndex": 1, "routeSummary": {
            "lengthInMeters": 6271, "travelTimeInSeconds": 1083, "trafficDelayInSeconds": 152,
            "departureTime": "2026-09-16T10:00:56+05:30"}},
        {"originIndex": 0, "destinationIndex": 2, "routeSummary": {
            "lengthInMeters": 15777, "travelTimeInSeconds": 1922, "trafficDelayInSeconds": 41}},
        {"originIndex": 1, "destinationIndex": 0, "routeSummary": {
            "lengthInMeters": 5117, "travelTimeInSeconds": 748, "trafficDelayInSeconds": 0}},
        {"originIndex": 1, "destinationIndex": 1, "routeSummary": {
            "lengthInMeters": 0, "travelTimeInSeconds": 0, "trafficDelayInSeconds": 0}},
        {"originIndex": 1, "destinationIndex": 2, "routeSummary": {
            "lengthInMeters": 14623, "travelTimeInSeconds": 1662, "trafficDelayInSeconds": 53}},
        {"originIndex": 2, "destinationIndex": 0, "routeSummary": {
            "lengthInMeters": 25024, "travelTimeInSeconds": 2274, "trafficDelayInSeconds": 41}},
        {"originIndex": 2, "destinationIndex": 1, "routeSummary": {
            "lengthInMeters": 23871, "travelTimeInSeconds": 1995, "trafficDelayInSeconds": 0}},
        {"originIndex": 2, "destinationIndex": 2, "routeSummary": {
            "lengthInMeters": 0, "travelTimeInSeconds": 0, "trafficDelayInSeconds": 0}},
    ],
    "statistics": {"totalCount": 9, "successes": 9, "failures": 0},
}

NODES = [
    Node(id="depot", name="Depot", type=NodeType.DEPOT, lat=28.5030, lng=77.0860, zone=Zone.INDUSTRIAL),
    Node(id="c01", name="MG Road", type=NodeType.CUSTOMER, lat=28.4795, lng=77.0805, demand=5, zone=Zone.OLD_CITY),
    Node(id="c02", name="Vatika", type=NodeType.CUSTOMER, lat=28.4089, lng=77.0400, demand=5, zone=Zone.SOHNA_ROAD),
]


def test_cells_become_directed_edges_without_diagonal():
    edges, failures, departure, failed = tomtom.cells_to_edges(NODES, RECORDED)
    assert failed == set()
    assert failures == 0
    assert len(edges) == 6  # 3 nodes -> 3*2 roads, diagonal dropped
    assert departure == "2026-09-16T10:00:56+05:30"
    pairs = {(e.source, e.target) for e in edges}
    assert ("depot", "depot") not in pairs
    assert ("depot", "c01") in pairs and ("c01", "depot") in pairs


def test_units_and_congestion_derivation():
    edges, _, _, _ = tomtom.cells_to_edges(NODES, RECORDED)
    e = next(x for x in edges if x.source == "depot" and x.target == "c01")
    assert e.distance_km == 6.271
    assert e.travel_time_min == round(1083 / 60, 2)
    # travel / (travel - delay): 1083 / 931
    assert e.congestion == round(1083 / 931, 3)
    clear = next(x for x in edges if x.source == "c01" and x.target == "depot")
    assert clear.congestion == 1.0  # zero delay reported


def test_problem_recovers_tomtom_delay_from_congestion():
    """Problem.delay = time - time/cong must equal TomTom's trafficDelay."""
    edges, _, _, _ = tomtom.cells_to_edges(NODES, RECORDED)
    g = square_graph()
    g.nodes = NODES
    g.edges = edges
    p = Problem(g)
    i, j = p.node_ids.index("depot"), p.node_ids.index("c01")
    assert abs(p.delay[i][j] - 152 / 60) < 0.02


def test_failed_cell_is_counted_not_crashed():
    broken = json.loads(json.dumps(RECORDED))
    broken["data"][1] = {"originIndex": 0, "destinationIndex": 1,
                         "detailedError": {"code": "NO_ROUTE_FOUND"}}
    edges, failures, _, failed = tomtom.cells_to_edges(NODES, broken)
    assert failures == 1
    assert len(edges) == 5
    assert failed == {"depot", "c01"}
    # A single failed cell cannot say which end is at fault: both are named.
    assert tomtom.culprits(NODES, broken) == {"depot", "c01"}


def test_culprit_is_the_node_that_fails_against_many_partners():
    """Huda City Centre on 16 Sep: every route INTO it failed, none out of it."""
    broken = json.loads(json.dumps(RECORDED))
    for cell in broken["data"]:
        if cell["destinationIndex"] == 1 and cell["originIndex"] != 1:
            cell.pop("routeSummary"); cell["detailedError"] = {"code": "NO_ROUTE_FOUND"}
    assert tomtom.culprits(NODES, broken) == {"c01"}


def test_transaction_formula_matches_tomtom_examples():
    assert tomtom.transactions_for(2, 3) == 6
    assert tomtom.transactions_for(5, 5) == 25
    assert tomtom.transactions_for(6, 100) == 500
    assert tomtom.transactions_for(50, 50) == 250
    assert tomtom.transactions_for(1000, 1000) == 5000


def test_simulated_is_the_default_and_unchanged():
    assert config.default_provider() in ("simulated", "tomtom")
    g = traffic.graph_for("ggn-10", "simulated")
    assert g is not None and g.source.provider == "simulated"
    assert len(g.edges) == 90
    # The benchmark instance must not drift: a known simulated edge.
    e = next(x for x in g.edges if x.source == "depot")
    assert e.congestion >= 1.0 and e.travel_time_min > 0


def test_unknown_provider_is_refused():
    try:
        traffic.graph_for("ggn-10", "google")
    except ValueError as err:
        assert "google" in str(err)
    else:
        raise AssertionError("expected ValueError")


def test_snapshot_round_trip(tmp_path=None):
    """Write a snapshot the way refresh does, read it back the way graph_for does."""
    import tempfile
    from pathlib import Path
    edges, _, _, _ = tomtom.cells_to_edges(NODES, RECORDED)
    original = config.SNAPSHOT_DIR
    try:
        config.SNAPSHOT_DIR = Path(tempfile.mkdtemp())
        payload = {
            "source": {"provider": "tomtom", "fetched_at": "2026-09-16T04:30:00+00:00",
                       "cells": 9, "transactions": 9, "endpoint": "sync"},
            "edges": [e.model_dump() for e in edges],
        }
        (config.SNAPSHOT_DIR / "blr-10.tomtom.json").write_text(json.dumps(payload))
        info = traffic.snapshot_info("blr-10")
        assert info.provider == "tomtom" and info.cells == 9
        assert traffic.snapshot_info("ggn-50") is None
    finally:
        config.SNAPSHOT_DIR = original
