"""Fitness: turning a route plan into one number the search can minimise.

An optimiser cannot compare two plans until "better" means something arithmetic.
This module is that definition. Every plan gets a single cost, and lower wins.

WHAT GOES INTO THE COST

The problem statement names the things that matter: travel time, distance,
congestion, and the number of vehicles used. All four are here, converted into a
common currency by a weight each, and added up. That is a weighted sum, the
standard way to fold several objectives into one:

    cost =  w_time        x total minutes driven
          + w_distance    x total kilometres driven
          + w_congestion  x minutes lost specifically to traffic
          + w_vehicle     x vans used
          + penalties

WHY CONGESTION APPEARS TWICE, ON PURPOSE

`travel_time_min` on every road already has congestion applied - a jammed road
is a slow road, and its minutes are counted in the first term. Charging for
congestion again in the third term is deliberate double-counting, and it is what
makes this a congestion-AWARE optimiser rather than merely a fast one. With the
third term at zero, a jammed road and a long clear road that take the same time
are worth the same. With it above zero, the plan prefers the clear road. That
preference is the behaviour SIH26137 is asking for, so it is priced explicitly
instead of left to emerge.

WHY THE WEIGHTS ARE NOT ALL 1

The four quantities are in different units - minutes, kilometres, and a count of
vans. Adding them raw would mean the objective is whatever happens to have the
biggest numbers. The weights are exchange rates, and every one of them is a
statement about the business the model claims to describe:

  time 1.0        the reference unit. One minute of driving costs 1.
  distance 0.5    every kilometre also costs fuel and wear, half a minute's worth.
  congestion 0.3  a minute lost in traffic hurts 30% more than a minute moving.
  vehicle 15.0    putting one more van on the road costs about 15 minutes of
                  driving: the driver, the vehicle, the depot handling.

They are defensible defaults, not laws, and Phase 4 exposes them as controls.
The one thing that must not change between algorithms is the weights themselves -
QPSO and PSO have to be scored by the identical function or the benchmark says
nothing.

PENALTIES

Two things a plan can get wrong. Both are priced far above any routing decision
so that no amount of clever driving can pay for them:

  overflow            using more vans than the fleet has
  capacity violation  a van carrying more than it can hold

The decoder can produce the first (see `encoding.py`). The second only happens
if a single stop demands more than one van holds, which network validation
should have caught first - it is checked here anyway rather than trusted.
"""

from dataclasses import dataclass
from typing import List, Sequence, Tuple

from .encoding import decode
from .problem import Problem


@dataclass(frozen=True)
class Weights:
    """Exchange rates between the things being optimised. See the module docstring."""

    time: float = 1.0
    distance: float = 0.5
    congestion: float = 0.3
    vehicle: float = 15.0
    overflow: float = 5000.0
    capacity_violation: float = 5000.0


@dataclass
class Solution:
    """A fully described route plan: what it is, and everything it costs."""

    routes: List[List[int]]
    loads: List[int]
    route_distance_km: List[float]
    route_time_min: List[float]
    route_delay_min: List[float]

    total_distance_km: float
    total_time_min: float
    congestion_delay_min: float
    vehicles_used: int
    overflow_vehicles: int
    overloaded_routes: int
    cost: float

    @property
    def feasible(self) -> bool:
        """True when the plan could actually be driven by the fleet as it exists."""
        return self.overflow_vehicles == 0 and self.overloaded_routes == 0

    @property
    def congestion_share(self) -> float:
        """Fraction of driving time that is traffic rather than travel. Reads well
        in a demo: "31% of this plan's time is spent sitting in jams."""
        if self.total_time_min <= 0:
            return 0.0
        return self.congestion_delay_min / self.total_time_min


def _walk(routes: Sequence[Sequence[int]], problem: Problem) -> Tuple[
    List[float], List[float], List[float], List[int]
]:
    """Drive every route and add up what it costs.

    Each route runs depot -> stops in order -> depot. The return leg is included
    because a delivery van that does not come back is not a delivery van.
    """
    distances: List[float] = []
    times: List[float] = []
    delays: List[float] = []
    loads: List[int] = []

    dist, time, delay, demand = problem.dist, problem.time, problem.delay, problem.demand

    for route in routes:
        if not route:
            continue
        d = t = g = 0.0
        load = 0
        here = 0  # the depot
        for node in route:
            d += dist[here][node]
            t += time[here][node]
            g += delay[here][node]
            load += demand[node]
            here = node
        d += dist[here][0]  # and back to the depot
        t += time[here][0]
        g += delay[here][0]

        distances.append(d)
        times.append(t)
        delays.append(g)
        loads.append(load)

    return distances, times, delays, loads


def _score(
    total_distance: float,
    total_time: float,
    total_delay: float,
    vehicles_used: int,
    overflow: int,
    overloaded: int,
    weights: Weights,
) -> float:
    """The cost formula itself, in one place so nothing can drift out of step with it."""
    return (
        weights.time * total_time
        + weights.distance * total_distance
        + weights.congestion * total_delay
        + weights.vehicle * vehicles_used
        + weights.overflow * overflow
        + weights.capacity_violation * overloaded
    )


def evaluate(
    routes: Sequence[Sequence[int]], problem: Problem, weights: Weights = Weights()
) -> Solution:
    """Score a route plan and report every component of the score.

    Use this for anything a human will read. The search loop uses `cost` instead,
    which computes the same number without building the report.
    """
    distances, times, delays, loads = _walk(routes, problem)

    vehicles_used = len(distances)
    overflow = max(0, vehicles_used - problem.vehicles)
    overloaded = sum(1 for load in loads if load > problem.capacity)

    total_distance = sum(distances)
    total_time = sum(times)
    total_delay = sum(delays)

    return Solution(
        routes=[list(r) for r in routes if r],
        loads=loads,
        route_distance_km=distances,
        route_time_min=times,
        route_delay_min=delays,
        total_distance_km=total_distance,
        total_time_min=total_time,
        congestion_delay_min=total_delay,
        vehicles_used=vehicles_used,
        overflow_vehicles=overflow,
        overloaded_routes=overloaded,
        cost=_score(
            total_distance, total_time, total_delay,
            vehicles_used, overflow, overloaded, weights,
        ),
    )


def cost(
    routes: Sequence[Sequence[int]], problem: Problem, weights: Weights = Weights()
) -> float:
    """The cost of a plan, and nothing else.

    This is the hot path - it runs once per particle per iteration, tens of
    thousands of times in a single solve - so it returns a bare float rather than
    a report object.
    """
    distances, times, delays, loads = _walk(routes, problem)
    vehicles_used = len(distances)
    return _score(
        sum(distances),
        sum(times),
        sum(delays),
        vehicles_used,
        max(0, vehicles_used - problem.vehicles),
        sum(1 for load in loads if load > problem.capacity),
        weights,
    )


def cost_of_keys(
    keys: Sequence[float], problem: Problem, weights: Weights = Weights()
) -> float:
    """Decode a particle's position and score it. The full objective function, as
    the search sees it: numbers in, one number out."""
    return cost(decode(keys, problem), problem, weights)
