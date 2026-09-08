"""Geography and the traffic model.

Two jobs: work out how far apart two places are, and work out how slow the road
between them is. Everything here is deterministic. Given the same network you
get the same edges every time, which is what makes the Phase 3 benchmark
meaningful: QPSO and PSO have to be solving the identical problem.
"""

import math
from typing import Dict, List, Tuple

from .models import Edge, Node, Zone

EARTH_RADIUS_KM = 6371.0

# Free-flow city driving speed. Congestion is applied on top of this.
BASE_SPEED_KMH = 32.0

# Roads are not straight lines. A journey between two points is longer than the
# distance as the crow flies; 1.35 is a common planning figure for Indian cities.
ROAD_WINDING_FACTOR = 1.35

# How slow it is to drive INTO each zone. Directed, because the morning commute
# into a business district is not the same as the drive out of it.
INBOUND_CONGESTION: Dict[Zone, float] = {
    Zone.CYBER_CITY: 2.30,   # Cyber Hub / Udyog Vihar at peak
    Zone.GOLF_COURSE: 1.75,
    Zone.OLD_CITY: 1.95,     # narrow roads, market traffic
    Zone.SOHNA_ROAD: 1.60,
    Zone.INDUSTRIAL: 1.30,
    Zone.HIGHWAY: 1.15,      # NH-48 moves, when it moves
}

# Leaving a zone is easier than entering it, but not free.
OUTBOUND_CONGESTION: Dict[Zone, float] = {
    Zone.CYBER_CITY: 1.55,
    Zone.GOLF_COURSE: 1.30,
    Zone.OLD_CITY: 1.50,
    Zone.SOHNA_ROAD: 1.25,
    Zone.INDUSTRIAL: 1.10,
    Zone.HIGHWAY: 1.05,
}


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two coordinates, in kilometres."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def road_distance_km(a: Node, b: Node) -> float:
    """Straight-line distance scaled up to something road-like."""
    return haversine_km(a.lat, a.lng, b.lat, b.lng) * ROAD_WINDING_FACTOR


def congestion_for(source: Node, target: Node) -> float:
    """Congestion multiplier for driving from `source` to `target`.

    Built from leaving the source zone and entering the target zone. Entering
    dominates, which is why the two directions of the same road differ.
    """
    out = OUTBOUND_CONGESTION[source.zone]
    inn = INBOUND_CONGESTION[target.zone]
    # Weighted toward the destination: getting in is the hard part.
    return round(0.35 * out + 0.65 * inn, 3)


def build_edges(nodes: List[Node]) -> List[Edge]:
    """Every ordered pair of nodes becomes a directed edge.

    A complete graph is the right model here: in a road network you can get from
    any stop to any other stop, and the cost of doing so is what the optimizer
    needs to know. For n nodes this is n*(n-1) edges.
    """
    edges: List[Edge] = []
    for a in nodes:
        for b in nodes:
            if a.id == b.id:
                continue
            dist = road_distance_km(a, b)
            cong = congestion_for(a, b)
            free_flow_min = (dist / BASE_SPEED_KMH) * 60.0
            edges.append(
                Edge(
                    source=a.id,
                    target=b.id,
                    distance_km=round(dist, 3),
                    travel_time_min=round(free_flow_min * cong, 2),
                    congestion=cong,
                )
            )
    return edges


def edge_count(n: int) -> int:
    return n * (n - 1)
