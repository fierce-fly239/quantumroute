#!/usr/bin/env python3
"""Solve a delivery network from the command line.

    python3 solve.py                          the 10-stop Gurugram network
    python3 solve.py --network ggn-50         the 49-stop one
    python3 solve.py --exact                  also compute the proven optimum
    python3 solve.py --seed 7 --iterations 1000
    python3 solve.py --json run.json          save the full result

Phase 2's deliverable is exactly this: QPSO solving a real instance with no
server, no browser and no API in the way. If it works here it works, and
everything after this is presentation.
"""

import argparse
import json
import sys
import time
from typing import List, Optional

from app import scenarios
from app.optimizer.exact import TooLargeForExact, exact_optimum, subsets_required
from app.optimizer.fitness import Solution, Weights
from app.optimizer.problem import Problem
from app.optimizer.qpso import IterationRecord, QPSOParams, optimize

BLOCKS = "▁▂▃▄▅▆▇█"


def sparkline(values: List[float], width: int = 60) -> str:
    """A convergence curve small enough to print. Down and to the right is good."""
    if not values:
        return ""
    step = max(1, len(values) // width)
    sampled = values[::step][:width]
    lo, hi = min(sampled), max(sampled)
    if hi - lo < 1e-9:
        return BLOCKS[0] * len(sampled)
    return "".join(
        BLOCKS[min(len(BLOCKS) - 1, int((v - lo) / (hi - lo) * len(BLOCKS)))] for v in sampled
    )


def print_plan(solution: Solution, problem: Problem, title: str) -> None:
    print(f"\n{title}")
    print("-" * len(title))
    for v, route in enumerate(solution.routes, start=1):
        stops = " -> ".join(problem.node_names[n] for n in route)
        print(
            f"  Van {v}  {solution.loads[v - 1]:>3}/{problem.capacity} units  "
            f"{solution.route_distance_km[v - 1]:>6.1f} km  "
            f"{solution.route_time_min[v - 1]:>6.1f} min"
        )
        print(f"         Depot -> {stops} -> Depot")

    status = "feasible" if solution.feasible else "INFEASIBLE"
    if solution.overflow_vehicles:
        status += f" ({solution.overflow_vehicles} van(s) over the fleet)"
    if solution.overloaded_routes:
        status += f" ({solution.overloaded_routes} van(s) overloaded)"

    print(
        f"\n  cost {solution.cost:.2f}   "
        f"{solution.total_time_min:.1f} min   "
        f"{solution.total_distance_km:.1f} km   "
        f"{solution.congestion_delay_min:.1f} min stuck in traffic "
        f"({solution.congestion_share:.0%})   "
        f"{solution.vehicles_used} van(s)   {status}"
    )


def to_dict(result, problem: Problem, exact: Optional[Solution]) -> dict:
    """The whole run as JSON. Phase 4 serves very nearly this over HTTP."""
    payload = {
        "network": {
            "id": problem.network_id,
            "name": problem.network_name,
            "customers": problem.customer_count,
            "vehicles": problem.vehicles,
            "capacity": problem.capacity,
            "total_demand": problem.total_demand,
        },
        "algorithm": result.algorithm,
        "params": {
            "particles": result.params.particles,
            "iterations": result.params.iterations,
            "alpha_start": result.params.alpha_start,
            "alpha_end": result.params.alpha_end,
            "c1": result.params.c1,
            "c2": result.params.c2,
            "seed": result.params.seed,
        },
        "weights": vars(result.weights),
        "evaluations": result.evaluations,
        "elapsed_s": round(result.elapsed_s, 4),
        "best": {
            "cost": result.best.cost,
            "total_time_min": result.best.total_time_min,
            "total_distance_km": result.best.total_distance_km,
            "congestion_delay_min": result.best.congestion_delay_min,
            "vehicles_used": result.best.vehicles_used,
            "feasible": result.best.feasible,
            "loads": result.best.loads,
            "routes": [[problem.node_ids[n] for n in route] for route in result.best.routes],
            "route_names": [
                [problem.node_names[n] for n in route] for route in result.best.routes
            ],
        },
        "history": [
            {"iteration": r.iteration, "best": r.best_cost, "mean": r.mean_cost, "alpha": r.alpha}
            for r in result.history
        ],
    }
    if exact is not None:
        payload["exact"] = {
            "cost": exact.cost,
            "gap_pct": 100.0 * (result.best.cost - exact.cost) / exact.cost,
        }
    return payload


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="QPSO vehicle route optimizer (SIH26137)")
    ap.add_argument("--network", default="ggn-10", choices=sorted(scenarios.NETWORKS))
    ap.add_argument("--particles", type=int, default=40, help="swarm size")
    ap.add_argument("--iterations", type=int, default=500)
    ap.add_argument("--seed", type=int, default=42, help="fix it to repeat a run exactly")
    ap.add_argument("--alpha-start", type=float, default=1.0)
    ap.add_argument("--alpha-end", type=float, default=0.5)
    ap.add_argument("--w-time", type=float, default=1.0)
    ap.add_argument("--w-distance", type=float, default=0.5)
    ap.add_argument("--w-congestion", type=float, default=0.3)
    ap.add_argument("--w-vehicle", type=float, default=15.0)
    ap.add_argument("--exact", action="store_true", help="also solve exactly, if small enough")
    ap.add_argument("--json", metavar="PATH", help="write the full result here")
    ap.add_argument("--quiet", action="store_true", help="no live progress")
    args = ap.parse_args(argv)

    graph = scenarios.get_graph(args.network)
    problem = Problem(graph)
    weights = Weights(
        time=args.w_time,
        distance=args.w_distance,
        congestion=args.w_congestion,
        vehicle=args.w_vehicle,
    )
    params = QPSOParams(
        particles=args.particles,
        iterations=args.iterations,
        alpha_start=args.alpha_start,
        alpha_end=args.alpha_end,
        seed=args.seed,
    )

    print(f"QuantumRoute  -  {problem.network_name}")
    print(
        f"  {problem.customer_count} stops, {problem.vehicles} vans x {problem.capacity} units, "
        f"{problem.total_demand} units of demand "
        f"({problem.total_demand / problem.fleet_capacity:.0%} of fleet capacity)"
    )
    print(
        f"  QPSO: {params.particles} particles x {params.iterations} iterations "
        f"= {params.particles * (params.iterations + 1):,} evaluations, "
        f"alpha {params.alpha_start} -> {params.alpha_end}, seed {params.seed}"
    )

    last = [0.0]

    def progress(rec: IterationRecord) -> None:
        now = time.perf_counter()
        if now - last[0] < 0.08 and rec.iteration != params.iterations - 1:
            return
        last[0] = now
        pct = 100 * (rec.iteration + 1) / params.iterations
        sys.stdout.write(
            f"\r  iteration {rec.iteration + 1:>5}/{params.iterations}  "
            f"({pct:>3.0f}%)  best {rec.best_cost:>10.2f}  "
            f"swarm mean {rec.mean_cost:>10.2f}  alpha {rec.alpha:.3f}   "
        )
        sys.stdout.flush()

    result = optimize(problem, weights, params, None if args.quiet else progress)
    if not args.quiet:
        print()

    print_plan(result.best, problem, "QPSO best plan")

    print("\nConvergence")
    print("-----------")
    print(f"  {sparkline([r.best_cost for r in result.history])}")
    print(
        f"  {result.initial_cost:.2f} at the start  ->  {result.best.cost:.2f}  "
        f"({result.improvement_pct:.1f}% better)"
    )
    settled = max(
        (r.iteration for r in result.history if r.best_cost > result.best.cost + 1e-9),
        default=0,
    )
    print(f"  last improvement at iteration {settled + 1} of {params.iterations}")
    print(f"  {result.evaluations:,} evaluations in {result.elapsed_s:.2f}s")

    exact: Optional[Solution] = None
    if args.exact:
        print("\nExact optimum")
        print("-------------")
        try:
            t = time.perf_counter()
            exact = exact_optimum(problem, weights)
            took = time.perf_counter() - t
        except TooLargeForExact as e:
            print(f"  Not computable. {e}")
        else:
            gap = 100.0 * (result.best.cost - exact.cost) / exact.cost
            print(
                f"  Proven best possible: {exact.cost:.2f} "
                f"({subsets_required(problem):,} subsets searched in {took:.3f}s)"
            )
            print(f"  QPSO came within {gap:.2f}% of it.")
            print_plan(exact, problem, "Optimal plan")

    if args.json:
        with open(args.json, "w") as fh:
            json.dump(to_dict(result, problem, exact), fh, indent=2)
        print(f"\nWrote {args.json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
