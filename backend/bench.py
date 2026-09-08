#!/usr/bin/env python3
"""Benchmark QPSO against classical PSO.

    python3 bench.py                             30 seeds on the 10-stop network
    python3 bench.py --network ggn-50 --runs 30  the 49-stop one
    python3 bench.py --csv out.csv --json out.json
    python3 bench.py --report                    also write an HTML page

Objective 3 of SIH26137 asks for QPSO to be compared against classical
metaheuristics. This is that comparison: both algorithms, same encoding, same
objective, same evaluation budget, same starting swarm per seed, 30 paired runs.
"""

import argparse
import csv
import json
import sys
import time
import webbrowser
from pathlib import Path
from typing import Optional

from app import scenarios
from app.optimizer.benchmark import Comparison, compare, to_csv_rows, to_dict
from app.optimizer.exact import TooLargeForExact, exact_optimum
from app.optimizer.fitness import Weights
from app.optimizer.problem import Problem


def bar(value: float, lo: float, hi: float, width: int = 34) -> str:
    """A horizontal bar, scaled between lo and hi. Lower cost is better, so a
    SHORTER bar is a better result."""
    if hi - lo < 1e-9:
        return "=" * (width // 2)
    filled = int(round((value - lo) / (hi - lo) * (width - 4))) + 4
    return "=" * max(1, min(width, filled))


def print_table(c: Comparison) -> None:
    q, p = c.qpso, c.pso
    lo = min(q.best, p.best)
    hi = max(q.worst, p.worst)

    print(f"\n{c.problem_name}  -  {len(c.seeds)} paired runs")
    budget = c.qpso_shape[0] * (c.qpso_shape[1] + 1)
    print(f"  {budget:,} evaluations per run, per algorithm")
    print(f"  QPSO {c.qpso_shape[0]}x{c.qpso_shape[1]}, alpha {c.alpha[0]} -> "
          f"{c.alpha[1]} {c.alpha_curve}")
    print(f"  PSO  {c.pso_shape[0]}x{c.pso_shape[1]}, inertia {c.inertia[0]} -> "
          f"{c.inertia[1]}")
    print(f"  seeds {c.seeds[0]}-{c.seeds[-1]}")
    if c.exact_cost is not None:
        print(f"  proven optimum: {c.exact_cost:.2f}")

    print("\n" + "-" * 76)
    print(f"{'':6} {'mean':>10} {'median':>10} {'best':>10} {'worst':>10} "
          f"{'std dev':>10} {'time/run':>10}")
    print("-" * 76)
    for s in (q, p):
        print(f"{s.algorithm.upper():6} {s.mean:>10.2f} {s.median:>10.2f} "
              f"{s.best:>10.2f} {s.worst:>10.2f} {s.stdev:>10.3f} "
              f"{s.mean_elapsed:>9.3f}s")
    print("-" * 76)

    print("\nMean cost  (shorter is better)")
    for s in (q, p):
        print(f"  {s.algorithm.upper():5} {bar(s.mean, lo, hi)}  {s.mean:.2f}")

    if c.exact_cost is not None:
        print("\nDistance above the proven optimum")
        for s in (q, p):
            gap = c.gap_to_exact(s)
            print(f"  {s.algorithm.upper():5} {gap:+.2f}%")

    w = c.wins
    print(f"\nHead to head on paired seeds:  QPSO {w['qpso']}   "
          f"PSO {w['pso']}   tied {w['tie']}")

    print("\nConvergence behaviour")
    # Each algorithm's own iteration count - they can differ now that the shapes
    # can differ at equal budget, and quoting the shared one produced lines like
    # "iteration 1504 of 500".
    for s, shape in ((q, c.qpso_shape), (p, c.pso_shape)):
        print(f"  {s.algorithm.upper():5} first reached its final answer at "
              f"iteration {s.mean_first_hit:.0f} of {shape[1]} on average")

    print("\nFeasibility")
    for s in (q, p):
        print(f"  {s.algorithm.upper():5} {s.feasible_count}/{len(s.runs)} runs "
              f"produced a plan the fleet can actually drive")

    print(f"\n{c.verdict()}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--network", default="ggn-10", choices=sorted(scenarios.NETWORKS))
    ap.add_argument("--runs", type=int, default=30, help="how many seeds")
    ap.add_argument("--particles", type=int, default=40)
    ap.add_argument("--iterations", type=int, default=500)
    ap.add_argument("--alpha", nargs=2, type=float, default=[1.0, 0.5],
                    metavar=("START", "END"), help="QPSO contraction-expansion schedule")
    ap.add_argument("--inertia", nargs=2, type=float, default=[0.9, 0.4],
                    metavar=("START", "END"), help="PSO inertia weight schedule")
    ap.add_argument("--qpso-shape", nargs=2, type=int, metavar=("PARTICLES", "ITERS"),
                    help="QPSO swarm shape; must match PSO's evaluation budget")
    ap.add_argument("--pso-shape", nargs=2, type=int, metavar=("PARTICLES", "ITERS"),
                    help="PSO swarm shape; must match QPSO's evaluation budget")
    ap.add_argument("--alpha-curve", choices=("linear", "quadratic"), default="linear")
    ap.add_argument("--weighted-mbest", action="store_true")
    ap.add_argument("--seed-from", type=int, default=1,
                    help="first seed; use 101 to run on the held-out set")
    ap.add_argument("--no-exact", action="store_true")
    ap.add_argument("--csv", metavar="PATH")
    ap.add_argument("--json", metavar="PATH")
    ap.add_argument("--report", action="store_true", help="write an HTML comparison page")
    ap.add_argument("--open", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    graph = scenarios.get_graph(args.network)
    if graph is None:
        raise SystemExit(f"No network '{args.network}'.")
    problem = Problem(graph)
    weights = Weights()

    exact_cost: Optional[float] = None
    if not args.no_exact:
        try:
            exact_cost = exact_optimum(problem, weights).cost
        except TooLargeForExact:
            exact_cost = None  # expected on the 49-stop network; reported as such

    seeds = list(range(args.seed_from, args.seed_from + args.runs))
    total = len(seeds) * 2
    done = 0
    started = time.perf_counter()

    def progress(algo: str, seed: int, cost: float) -> None:
        nonlocal done
        done += 1
        if not args.quiet:
            print(f"\r  {done}/{total} runs  ({algo} seed {seed}: {cost:.2f})"
                  f"{' ' * 12}", end="", file=sys.stderr, flush=True)

    c = compare(
        problem, seeds=seeds, particles=args.particles, iterations=args.iterations,
        weights=weights, exact_cost=exact_cost, on_run=progress,
        alpha=(args.alpha[0], args.alpha[1]),
        inertia=(args.inertia[0], args.inertia[1]),
        qpso_shape=tuple(args.qpso_shape) if args.qpso_shape else None,
        pso_shape=tuple(args.pso_shape) if args.pso_shape else None,
        alpha_curve=args.alpha_curve,
        weighted_mbest=args.weighted_mbest,
    )
    if not args.quiet:
        print(f"\r  {total} runs in {time.perf_counter() - started:.1f}s"
              f"{' ' * 24}", file=sys.stderr)

    print_table(c)

    root = Path(__file__).resolve().parent.parent / "results"
    if args.csv or args.json or args.report:
        root.mkdir(parents=True, exist_ok=True)

    if args.csv:
        path = Path(args.csv)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerows(to_csv_rows(c))
        print(f"\nCSV  -> {path}")

    if args.json:
        path = Path(args.json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(to_dict(c), indent=2), encoding="utf-8")
        print(f"JSON -> {path}")

    if args.report:
        from bench_report import honest_section, write_report
        out = root / f"{args.network}-benchmark.html"
        data = to_dict(c)
        write_report(data, out, honest_section(data))
        print(f"HTML -> {out}")
        if args.open:
            webbrowser.open(out.as_uri())


if __name__ == "__main__":
    main()
