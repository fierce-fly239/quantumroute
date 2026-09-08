"""Running solves in the background so the browser can watch them.

WHY THIS IS NOT JUST A FUNCTION CALL

A solve takes between 0.1 and 2 seconds. That is fast enough to serve from a
single blocking request and slow enough that doing so would be a lie: the page
would sit dead and then flash a finished answer, which shows none of the
convergence behaviour the project is actually about.

So a solve becomes a JOB. The browser starts one, gets an id back immediately,
then polls for progress and finally collects the result. The Run page uses that
to show the iteration counter and the curve building up live.

WHY IN-MEMORY AND NOT A REAL QUEUE

Celery, Redis, a database - all correct for production and all wrong for this.
This runs on one laptop for one demo, and every one of those adds a service that
can fail on the morning of the 10th. A dictionary and a lock have no such
failure mode. The cost is that jobs vanish when the server restarts, which for a
demo is not a cost at all.

Jobs are capped and old ones evicted, so a long demo session cannot grow memory
without limit.
"""

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional

from .optimizer.encoding import decode
from .optimizer.fitness import Solution, Weights
from .optimizer.problem import Problem
from .optimizer.pso import PSOParams
from .optimizer.pso import optimize as pso_optimize
from .optimizer.qpso import IterationRecord, QPSOParams
from .optimizer.qpso import optimize as qpso_optimize

Algorithm = Literal["qpso", "pso", "both"]
Status = Literal["queued", "running", "done", "failed"]

# Enough for a long demo session, small enough that memory cannot run away.
MAX_JOBS = 40


@dataclass
class AlgorithmRun:
    """One algorithm's contribution to a job."""

    algorithm: str
    best: Optional[Solution] = None
    best_keys: List[float] = field(default_factory=list)
    curve: List[float] = field(default_factory=list)
    mean_curve: List[float] = field(default_factory=list)
    alpha_curve: List[float] = field(default_factory=list)
    evaluations: int = 0
    elapsed_s: float = 0.0
    start_cost: Optional[float] = None
    first_hit_iteration: int = 0


@dataclass
class Job:
    id: str
    network_id: str
    algorithm: Algorithm
    particles: int
    iterations: int
    seed: int
    weights: Weights
    alpha: tuple
    inertia: tuple
    weighted_mbest: bool = False
    alpha_curve: str = "linear"

    status: Status = "queued"
    created_at: float = field(default_factory=time.time)
    error: Optional[str] = None

    # Live progress, written by the worker thread and read by pollers.
    phase: str = ""
    iteration: int = 0
    total_iterations: int = 0
    best_cost: Optional[float] = None
    live_curve: List[float] = field(default_factory=list)

    runs: Dict[str, AlgorithmRun] = field(default_factory=dict)

    @property
    def progress(self) -> float:
        """0.0 to 1.0 across the whole job, both algorithms included."""
        legs = 2 if self.algorithm == "both" else 1
        if self.total_iterations <= 0:
            return 0.0
        done_legs = len(self.runs)
        within = self.iteration / self.total_iterations
        return min(1.0, (done_legs + within) / legs) if legs else 0.0


_jobs: Dict[str, Job] = {}
_lock = threading.Lock()


def _evict_if_needed() -> None:
    """Drop the oldest finished jobs once the table is full. Called with the lock
    held. Running jobs are never evicted - only jobs nobody is waiting on."""
    if len(_jobs) <= MAX_JOBS:
        return
    finished = sorted(
        (j for j in _jobs.values() if j.status in ("done", "failed")),
        key=lambda j: j.created_at,
    )
    for job in finished[: len(_jobs) - MAX_JOBS]:
        _jobs.pop(job.id, None)


def get(job_id: str) -> Optional[Job]:
    with _lock:
        return _jobs.get(job_id)


def _run_one(job: Job, problem: Problem, algorithm: str) -> AlgorithmRun:
    """Run a single algorithm, streaming progress onto the job as it goes."""
    job.phase = algorithm
    job.iteration = 0

    curve: List[float] = []
    means: List[float] = []
    alphas: List[float] = []

    def on_iteration(rec: IterationRecord) -> None:
        # Written without the lock: these are plain assignments to a job only
        # this thread writes, and readers tolerate a slightly stale value. Taking
        # the lock once per iteration would serialise the search against every
        # poll for no benefit.
        job.iteration = rec.iteration + 1
        job.best_cost = rec.best_cost
        curve.append(rec.best_cost)
        means.append(rec.mean_cost)
        alphas.append(rec.alpha)
        # A sampled copy for the live chart; the full curve goes in the result.
        if rec.iteration % max(1, job.total_iterations // 120) == 0:
            job.live_curve = list(curve)

    if algorithm == "qpso":
        result = qpso_optimize(
            problem, job.weights,
            QPSOParams(particles=job.particles, iterations=job.iterations,
                       seed=job.seed, alpha_start=job.alpha[0], alpha_end=job.alpha[1],
                       weighted_mbest=job.weighted_mbest, alpha_curve=job.alpha_curve),
            on_iteration=on_iteration,
        )
    else:
        result = pso_optimize(
            problem, job.weights,
            PSOParams(particles=job.particles, iterations=job.iterations,
                      seed=job.seed, inertia_start=job.inertia[0],
                      inertia_end=job.inertia[1]),
            on_iteration=on_iteration,
        )

    final = result.best.cost
    first_hit = next((i for i, c in enumerate(curve) if c <= final + 1e-9), 0)

    return AlgorithmRun(
        algorithm=algorithm,
        best=result.best,
        best_keys=list(result.best_keys),
        curve=curve,
        mean_curve=means,
        alpha_curve=alphas,
        evaluations=result.evaluations,
        elapsed_s=result.elapsed_s,
        start_cost=result.initial_cost,
        first_hit_iteration=first_hit,
    )


def _worker(job: Job, problem: Problem) -> None:
    try:
        job.status = "running"
        legs = ["qpso", "pso"] if job.algorithm == "both" else [job.algorithm]
        for algo in legs:
            run = _run_one(job, problem, algo)
            # Publish the finished leg only once it is complete, so a poller
            # never sees a half-built run.
            with _lock:
                job.runs[algo] = run
        job.status = "done"
        job.phase = ""
    except Exception as exc:  # noqa: BLE001 - the message goes to the browser
        job.status = "failed"
        job.error = f"{type(exc).__name__}: {exc}"


def start(
    problem: Problem,
    network_id: str,
    algorithm: Algorithm = "qpso",
    particles: int = 40,
    iterations: int = 500,
    seed: int = 42,
    weights: Optional[Weights] = None,
    alpha: tuple = (0.9, 0.4),
    inertia: tuple = (0.729, 0.729),
    weighted_mbest: bool = False,
    alpha_curve: str = "linear",
) -> Job:
    """Queue a solve and return immediately with the job."""
    job = Job(
        id=uuid.uuid4().hex[:12],
        network_id=network_id,
        algorithm=algorithm,
        particles=particles,
        iterations=iterations,
        seed=seed,
        weights=weights or Weights(),
        alpha=alpha,
        inertia=inertia,
        weighted_mbest=weighted_mbest,
        alpha_curve=alpha_curve,
        total_iterations=iterations,
    )
    with _lock:
        _jobs[job.id] = job
        _evict_if_needed()

    thread = threading.Thread(target=_worker, args=(job, problem), daemon=True)
    thread.start()
    return job


def routes_with_places(run: AlgorithmRun, problem: Problem, coords: dict) -> List[dict]:
    """A finished run's routes, expanded into something the map can draw:
    names, coordinates, and the depot legs at both ends."""
    if run.best is None:
        return []
    depot = coords[problem.node_ids[0]]
    out = []
    for i, route in enumerate(run.best.routes):
        out.append({
            "van": i + 1,
            "load": run.best.loads[i],
            "distanceKm": round(run.best.route_distance_km[i], 2),
            "timeMin": round(run.best.route_time_min[i], 1),
            "delayMin": round(run.best.route_delay_min[i], 1),
            "stops": [
                {"name": problem.node_names[n], "at": coords[problem.node_ids[n]],
                 "demand": problem.demand[n]}
                for n in route
            ],
            "path": [depot] + [coords[problem.node_ids[n]] for n in route] + [depot],
        })
    return out
