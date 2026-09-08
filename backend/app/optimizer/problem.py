"""The optimizer's view of a delivery network.

`NetworkGraph` is the shape the API serves: pydantic objects, string ids, and a
flat list of edges. That shape is right for JSON and wrong for an inner loop.
A 300-iteration run with 30 particles evaluates 9,000 candidate solutions, and
each one walks every road it uses. Looking edges up by string id that many times
is wasted work.

`Problem` is the same information, flattened once, before the search starts:
integer indices instead of string ids, and square matrices instead of an edge
list. Built once, read millions of times.

Two conventions hold everywhere in the optimizer:

  * Node index 0 is ALWAYS the depot.
  * Customers are node indices 1..n, where n is `customer_count`.

The second one matters when reading `encoding.py`: a particle's position vector
has length n, and position `k` in that vector belongs to node index `k + 1`.
"""

from typing import List

from ..models import NetworkGraph, NodeType


class Problem:
    """A capacitated vehicle routing problem, ready to be solved.

    Attributes that the rest of the optimizer relies on:

      size            total nodes, depot included
      customer_count  nodes that need a delivery (size - 1)
      demand[i]       units to drop at node i; demand[0] is 0, the depot
      dist[i][j]      kilometres from node i to node j
      time[i][j]      minutes from i to j, congestion already applied
      delay[i][j]     of those minutes, how many are traffic rather than distance
      cong[i][j]      the congestion multiplier itself, 1.0 being a clear road
      vehicles        vans in the fleet
      capacity        units one van can carry
    """

    def __init__(self, graph: NetworkGraph) -> None:
        depots = [nd for nd in graph.nodes if nd.type == NodeType.DEPOT]
        customers = [nd for nd in graph.nodes if nd.type != NodeType.DEPOT]

        if len(depots) != 1:
            raise ValueError(
                f"A route plan needs exactly one depot to leave from and return to; "
                f"this network has {len(depots)}."
            )
        if not customers:
            raise ValueError("Nothing to deliver: the network has no customer stops.")

        # Depot first, then customers in the order the network listed them. This
        # ordering is the whole reason index 0 can be assumed to be the depot.
        ordered = depots + customers

        self.network_id: str = graph.meta.id
        self.network_name: str = graph.meta.name
        self.node_ids: List[str] = [nd.id for nd in ordered]
        self.node_names: List[str] = [nd.name for nd in ordered]
        self.demand: List[int] = [nd.demand for nd in ordered]

        self.size: int = len(ordered)
        self.customer_count: int = len(customers)
        self.vehicles: int = graph.meta.fleet.vehicles
        self.capacity: int = graph.meta.fleet.capacity
        self.total_demand: int = sum(self.demand)

        index_of = {nd.id: i for i, nd in enumerate(ordered)}
        n = self.size
        missing = float("inf")

        self.dist: List[List[float]] = [[missing] * n for _ in range(n)]
        self.time: List[List[float]] = [[missing] * n for _ in range(n)]
        self.cong: List[List[float]] = [[missing] * n for _ in range(n)]

        for e in graph.edges:
            i, j = index_of.get(e.source), index_of.get(e.target)
            if i is None or j is None:
                raise ValueError(
                    f"Road '{e.source}' -> '{e.target}' points at a stop that is not "
                    f"in this network."
                )
            self.dist[i][j] = e.distance_km
            self.time[i][j] = e.travel_time_min
            self.cong[i][j] = e.congestion

        for i in range(n):
            self.dist[i][i] = 0.0
            self.time[i][i] = 0.0
            self.cong[i][i] = 1.0

        # Every stop must be reachable from every other stop. If one road is
        # missing the optimizer would silently price a route at infinity and the
        # search would go strange. Better to refuse the network up front.
        for i in range(n):
            for j in range(n):
                if self.time[i][j] == missing:
                    raise ValueError(
                        f"No road modelled from '{self.node_names[i]}' to "
                        f"'{self.node_names[j]}'. The optimizer needs a complete graph."
                    )

        # Split each journey's minutes into "minutes because it is far" and
        # "minutes because it is jammed". travel_time = free_flow x congestion,
        # so the free-flow part is time / congestion and the rest is the delay.
        # Precomputed here so the inner loop never divides.
        self.delay: List[List[float]] = [
            [self.time[i][j] - (self.time[i][j] / self.cong[i][j]) for j in range(n)]
            for i in range(n)
        ]

    @property
    def fleet_capacity(self) -> int:
        """Total units the whole fleet can carry in one wave."""
        return self.vehicles * self.capacity

    @property
    def min_vehicles_needed(self) -> int:
        """The fewest vans that could possibly carry the demand, ignoring geography.

        A lower bound, not a plan: it assumes every van can be packed perfectly
        full, which routing almost never allows. Useful as a sanity floor.
        """
        return -(-self.total_demand // self.capacity)  # ceiling division

    def __repr__(self) -> str:
        return (
            f"<Problem {self.network_id}: {self.customer_count} stops, "
            f"{self.vehicles} vans x {self.capacity} units, "
            f"{self.total_demand} units of demand>"
        )
