"""The provably optimal answer, for instances small enough to have one.

WHY A SECOND SOLVER EXISTS

A metaheuristic gives you an answer, not a guarantee. QPSO will happily report
its best plan whether that plan is world-class or mediocre, and by itself the
number means nothing - "cost 183" is only good or bad next to something.

This module supplies the something. For a small instance it computes the true
optimum by exhaustive dynamic programming, so QPSO's answer can be reported as a
percentage off a proven floor rather than as a bare figure. That turns an
unfalsifiable claim into a measurement.

WHY IT IS NOT THE WHOLE PROJECT

Because it stops working almost immediately.

The method below considers every subset of customers: 2^n of them. At 9 stops
that is 512 subsets and the answer lands in milliseconds. At 20 stops it is a
million. At 49 stops - the size of the second built-in network, and a small
delivery round by any real standard - it is 562,949,953,421,312, and no amount
of waiting or hardware fixes that.

THAT is what NP-hard means, made concrete: not "slow", but a cost that multiplies
by two for every single stop added, so that the exact method is finished as a
practical tool long before the problem gets interesting. It is the entire reason
a metaheuristic is the right tool for the real instance, and the reason this file
carries a hard cap instead of a progress bar.

HOW IT WORKS

Two stages of dynamic programming.

  1. Held-Karp, for each capacity-feasible subset S of customers: the cheapest
     single van round trip that leaves the depot, visits exactly the stops in S,
     and returns. Built up by remembering, for every subset and every possible
     last stop, the cheapest way to have arrived there.

  2. Set partitioning: split all customers into vans. best[S][v] is the cheapest
     way to serve the stops in S using exactly v vans, found by trying every
     way to peel one van's round trip off S and solving the rest.

Both stages price roads with a single combined weight - the weighted sum from
`fitness.py` collapsed into one number per road, which is legitimate because
time, distance and congestion delay are all additive along a route. Per-van cost
is added once per van in stage 2.
"""

from itertools import combinations
from typing import Dict, List, Optional, Tuple

from .fitness import Solution, Weights, evaluate
from .problem import Problem

# Above this the subset table stops fitting in memory and in a lifetime.
# 18 customers is 262,144 subsets, which already takes a while; the default of
# 15 keeps the verification honest and instant.
MAX_EXACT_CUSTOMERS = 15


class TooLargeForExact(Exception):
    """Raised when an instance is beyond exhaustive search - which is most of them."""


def combined_edge_weights(problem: Problem, weights: Weights) -> List[List[float]]:
    """Fold time, distance and congestion delay into one cost per road.

    Valid because all three accumulate along a route, so a route's weighted cost
    equals the sum of its roads' weighted costs. Vehicle cost is not in here: it
    is charged per van, not per road, and is added in stage 2.
    """
    n = problem.size
    return [
        [
            weights.time * problem.time[i][j]
            + weights.distance * problem.dist[i][j]
            + weights.congestion * problem.delay[i][j]
            for j in range(n)
        ]
        for i in range(n)
    ]


def exact_optimum(
    problem: Problem,
    weights: Weights = Weights(),
    max_customers: int = MAX_EXACT_CUSTOMERS,
) -> Solution:
    """The genuinely best possible route plan, or an explanation of why not.

    Unlike QPSO this searches every legal plan, so its answer is a floor: nothing
    can beat it. Plans needing more vans than the fleet has are excluded outright
    rather than penalised - here we can afford to only consider the real ones.
    """
    n = problem.customer_count
    if n > max_customers:
        raise TooLargeForExact(
            f"{n} stops means 2^{n} = {2 ** n:,} subsets to examine. Exhaustive "
            f"search is only honest up to about {max_customers} stops - past that "
            f"the exact method is not slow, it is impossible, which is exactly why "
            f"this project uses a metaheuristic. Use QPSO instead."
        )

    w = combined_edge_weights(problem, weights)
    demand = problem.demand
    capacity = problem.capacity
    full = (1 << n) - 1

    # Bit k of a mask stands for customer node index k+1.
    subset_demand = [0] * (full + 1)
    for mask in range(1, full + 1):
        low = mask & -mask
        k = low.bit_length() - 1
        subset_demand[mask] = subset_demand[mask ^ low] + demand[k + 1]

    # --- Stage 1: cheapest single-van round trip for each feasible subset -----
    # held[mask][last] = cheapest way to leave the depot, cover `mask`, and be
    # standing at `last`. The return leg to the depot is added afterwards.
    tour_cost: Dict[int, float] = {}
    tour_path: Dict[int, List[int]] = {}

    held: Dict[int, List[Optional[float]]] = {}
    parent: Dict[int, List[Optional[int]]] = {}

    feasible = [m for m in range(1, full + 1) if subset_demand[m] <= capacity]

    for mask in feasible:
        best_cost: List[Optional[float]] = [None] * n
        best_prev: List[Optional[int]] = [None] * n
        bits = [k for k in range(n) if mask >> k & 1]
        for k in bits:
            prev_mask = mask ^ (1 << k)
            node = k + 1
            if prev_mask == 0:
                best_cost[k] = w[0][node]  # straight out from the depot
                best_prev[k] = None
                continue
            prev_row = held.get(prev_mask)
            if prev_row is None:
                continue  # a sub-route that was itself infeasible
            cheapest = None
            via = None
            for j in range(n):
                c = prev_row[j]
                if c is None:
                    continue
                total = c + w[j + 1][node]
                if cheapest is None or total < cheapest:
                    cheapest = total
                    via = j
            best_cost[k] = cheapest
            best_prev[k] = via
        held[mask] = best_cost
        parent[mask] = best_prev

        # Close the loop back to the depot and keep the best ending.
        closed = None
        end = None
        for k in bits:
            c = best_cost[k]
            if c is None:
                continue
            total = c + w[k + 1][0]
            if closed is None or total < closed:
                closed = total
                end = k
        if closed is not None:
            tour_cost[mask] = closed
            # Walk the parent pointers back to recover the visiting order.
            path: List[int] = []
            m, k = mask, end
            while k is not None:
                path.append(k + 1)
                nxt = parent[m][k]
                m ^= 1 << k
                k = nxt
            tour_path[mask] = list(reversed(path))

    # --- Stage 2: split the customers between vans ---------------------------
    # best[mask][v] = cheapest way to serve `mask` with exactly v vans.
    max_v = problem.vehicles
    NO = float("inf")
    best = [[NO] * (max_v + 1) for _ in range(full + 1)]
    choice: List[List[Optional[int]]] = [[None] * (max_v + 1) for _ in range(full + 1)]
    best[0][0] = 0.0

    for mask in range(1, full + 1):
        # Fix the lowest-numbered stop into whichever van we peel off next. Every
        # partition puts it in some van, so this loses nothing and stops the same
        # partition being counted once per ordering of its vans.
        low = mask & -mask
        rest = mask ^ low
        sub = rest
        while True:
            van = sub | low
            t = tour_cost.get(van)
            if t is not None:
                remainder = mask ^ van
                for v in range(1, max_v + 1):
                    prior = best[remainder][v - 1]
                    if prior == NO:
                        continue
                    total = prior + t + weights.vehicle
                    if total < best[mask][v]:
                        best[mask][v] = total
                        choice[mask][v] = van
            if sub == 0:
                break
            sub = (sub - 1) & rest

    v_best = min(range(1, max_v + 1), key=lambda v: best[full][v])
    if best[full][v_best] == NO:
        raise ValueError(
            f"No legal plan exists: {problem.total_demand} units of demand cannot fit "
            f"in {problem.vehicles} vans of {problem.capacity} units."
        )

    # Recover the actual vans.
    routes: List[List[int]] = []
    mask, v = full, v_best
    while mask:
        van = choice[mask][v]
        assert van is not None
        routes.append(tour_path[van])
        mask ^= van
        v -= 1

    return evaluate(routes, problem, weights)


def exact_is_feasible(problem: Problem, max_customers: int = MAX_EXACT_CUSTOMERS) -> bool:
    """Whether this instance is small enough to solve exactly."""
    return problem.customer_count <= max_customers


def subsets_required(problem: Problem) -> int:
    """How many subsets an exhaustive search would have to look at. Prints well in
    a demo when the number is astronomical."""
    return 2 ** problem.customer_count
