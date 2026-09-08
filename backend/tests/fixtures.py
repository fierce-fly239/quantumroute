"""A tiny network whose right answers can be worked out by hand.

The built-in Gurugram scenarios are useful for realism and useless for testing:
nobody can say from reading the file what the correct cost of a route through
them is. This one is four nodes on a square with round numbers, so a test can
assert an exact figure rather than "roughly".
"""

from app.models import Edge, Fleet, NetworkGraph, NetworkMeta, Node, NodeType, Zone


def square_graph(vehicles: int = 2, capacity: int = 10) -> NetworkGraph:
    """Depot plus three customers. Every road is 10 km, 20 minutes, congestion 2.0.

    Uniform roads mean the cost of a plan depends only on HOW MANY road segments
    it uses, which makes every expected value in the tests arithmetic a reader
    can check: a van serving k stops drives k+1 segments.

    Demands are 6, 5 and 4 - total 15 against a fleet capacity of 20, but no two
    of them fit in one 10-unit van together except 6+4. That makes the packing
    behaviour observable instead of incidental.
    """
    nodes = [
        Node(id="d0", name="Depot", type=NodeType.DEPOT, lat=28.50, lng=77.00,
             demand=0, zone=Zone.INDUSTRIAL),
        Node(id="c1", name="Alpha", type=NodeType.CUSTOMER, lat=28.51, lng=77.00,
             demand=6, zone=Zone.INDUSTRIAL),
        Node(id="c2", name="Bravo", type=NodeType.CUSTOMER, lat=28.51, lng=77.01,
             demand=5, zone=Zone.INDUSTRIAL),
        Node(id="c3", name="Charlie", type=NodeType.CUSTOMER, lat=28.50, lng=77.01,
             demand=4, zone=Zone.INDUSTRIAL),
    ]
    edges = [
        Edge(source=a.id, target=b.id, distance_km=10.0, travel_time_min=20.0, congestion=2.0)
        for a in nodes
        for b in nodes
        if a.id != b.id
    ]
    meta = NetworkMeta(
        id="square", name="Unit square", city="Test", description="Hand-checkable fixture",
        node_count=len(nodes), customer_count=3,
        fleet=Fleet(vehicles=vehicles, capacity=capacity),
        total_demand=15,
    )
    return NetworkGraph(meta=meta, nodes=nodes, edges=edges)


def tight_graph() -> NetworkGraph:
    """Four customers whose demands fit the fleet perfectly - but only in the
    right order.

    Demands 7, 3, 7, 3 into two 10-unit vans. Total 20 against a fleet capacity of
    20, so a perfect packing exists: pair each 7 with a 3. But filling vans in the
    visiting order 7, 7, 3, 3 closes the first van after one stop and needs three
    vans for work two could do.

    That is the decoder's known weakness in its purest form, and the reason
    `fitness.py` charges for vans beyond the fleet: the search has to be pushed
    toward orderings that pack, because the decoder will not pack for it.
    """
    nodes = [
        Node(id="d0", name="Depot", type=NodeType.DEPOT, lat=28.50, lng=77.00,
             demand=0, zone=Zone.INDUSTRIAL),
        Node(id="c1", name="Heavy A", type=NodeType.CUSTOMER, lat=28.51, lng=77.00,
             demand=7, zone=Zone.INDUSTRIAL),
        Node(id="c2", name="Light A", type=NodeType.CUSTOMER, lat=28.51, lng=77.01,
             demand=3, zone=Zone.INDUSTRIAL),
        Node(id="c3", name="Heavy B", type=NodeType.CUSTOMER, lat=28.50, lng=77.01,
             demand=7, zone=Zone.INDUSTRIAL),
        Node(id="c4", name="Light B", type=NodeType.CUSTOMER, lat=28.49, lng=77.00,
             demand=3, zone=Zone.INDUSTRIAL),
    ]
    edges = [
        Edge(source=a.id, target=b.id, distance_km=10.0, travel_time_min=20.0, congestion=2.0)
        for a in nodes
        for b in nodes
        if a.id != b.id
    ]
    meta = NetworkMeta(
        id="tight", name="Tight fleet", city="Test", description="Packing fixture",
        node_count=len(nodes), customer_count=4,
        fleet=Fleet(vehicles=2, capacity=10),
        total_demand=20,
    )
    return NetworkGraph(meta=meta, nodes=nodes, edges=edges)
