"""Data model for the road network.

SIH26137 asks for the transportation network to be modelled as a weighted
directed graph. That is what these types describe:

  Node  - a place. Either the depot every van leaves from and returns to, or a
          customer stop with a demand (how many units get dropped there).
  Edge  - a one-way road between two places, carrying the three weights the
          problem statement names: distance, travel time, and congestion.

Edges are directed and deliberately asymmetric: driving *into* Cyber City in the
morning is not the same cost as driving out of it. A directed graph is what lets
us say that.
"""

from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class NodeType(str, Enum):
    DEPOT = "depot"
    CUSTOMER = "customer"


class Zone(str, Enum):
    """Traffic zones. Congestion is modelled between zones rather than per road,
    because we do not have per-road traffic data and inventing it would be worse
    than modelling it openly."""

    CYBER_CITY = "cyber-city"
    GOLF_COURSE = "golf-course"
    OLD_CITY = "old-city"
    SOHNA_ROAD = "sohna-road"
    INDUSTRIAL = "industrial"
    HIGHWAY = "highway"


class Node(BaseModel):
    id: str = Field(..., description="Unique within a network, e.g. 'c07'")
    name: str = Field(..., description="Human-readable, e.g. 'DLF Cyber Hub'")
    type: NodeType
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    demand: int = Field(0, ge=0, description="Units to drop here. Always 0 at the depot.")
    zone: Zone


class Edge(BaseModel):
    """A one-way road. `travel_time_min` already has congestion applied, so the
    optimizer can use it directly without re-deriving anything."""

    source: str
    target: str
    distance_km: float
    travel_time_min: float
    congestion: float = Field(
        ..., ge=1.0, description="Multiplier on free-flow time. 1.0 is clear road."
    )


class Fleet(BaseModel):
    vehicles: int = Field(..., gt=0, description="Vans available")
    capacity: int = Field(..., gt=0, description="Units each van can carry")


class NetworkMeta(BaseModel):
    id: str
    name: str
    city: str
    description: str
    node_count: int
    customer_count: int
    fleet: Fleet
    total_demand: int


class Network(BaseModel):
    """A network without its edges. This is what the map needs."""

    meta: NetworkMeta
    nodes: List[Node]


class EdgeSource(BaseModel):
    """Where a graph's travel times came from. `simulated` is the zone model in
    geo.py; `tomtom` is a frozen snapshot of live road data (see traffic.py)."""

    provider: Literal["simulated", "tomtom"]
    fetched_at: Optional[str] = None      # UTC ISO time the snapshot was taken
    departure_time: Optional[str] = None  # the local time TomTom priced the roads for
    cells: Optional[int] = None
    transactions: Optional[int] = None
    endpoint: Optional[str] = None
    fetch_seconds: Optional[float] = None


class NetworkGraph(Network):
    """A network with its full edge set. This is what the optimizer needs."""

    edges: List[Edge]
    source: Optional[EdgeSource] = None


class ValidationIssue(BaseModel):
    severity: Literal["error", "warning"]
    message: str
    hint: Optional[str] = None


class ValidationResult(BaseModel):
    valid: bool
    issues: List[ValidationIssue]
