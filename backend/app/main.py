"""QuantumRoute Optimizer - API server.

SIH26137. Phase 2: the road network is modelled, served and validated, and
QPSO solves it from the command line (`python3 solve.py`). Wiring the optimizer
to HTTP is Phase 4 - it deliberately has no dependency on this file.
"""

from typing import Dict, List, Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import jobs, scenarios
from .models import Network, NetworkGraph, NetworkMeta, ValidationResult
from .optimizer.exact import TooLargeForExact, exact_optimum
from .optimizer.fitness import Weights
from .optimizer.problem import Problem
from .validation import validate_network

app = FastAPI(
    title="QuantumRoute Optimizer",
    description=(
        "Quantum-inspired vehicle route optimization for SIH26137. "
        "Solves a capacitated vehicle routing problem with congestion-weighted "
        "roads using Quantum Particle Swarm Optimization, benchmarked against "
        "classical Particle Swarm Optimization."
    ),
    version="0.4.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Health(BaseModel):
    status: str
    service: str
    version: str
    phase: str


@app.get("/api/health", response_model=Health, tags=["system"])
def health() -> Health:
    """Liveness check. The frontend header calls this to show connection state."""
    return Health(status="ok", service="quantumroute", version="0.4.0", phase="4 - optimizer wired to the web app")


@app.get("/api/networks", response_model=List[NetworkMeta], tags=["network"])
def list_networks() -> List[NetworkMeta]:
    """Summaries of every built-in scenario, for the picker."""
    return [n.meta for n in scenarios.NETWORKS.values()]


@app.get("/api/networks/{network_id}", response_model=Network, tags=["network"])
def get_network(network_id: str) -> Network:
    """One network's nodes. This is what the map draws.

    Edges are excluded deliberately: a 50-stop network has 2,450 of them and the
    map has no use for any. The optimizer gets them from /graph instead.
    """
    net = scenarios.get_network(network_id)
    if net is None:
        raise HTTPException(
            status_code=404,
            detail=f"No network '{network_id}'. Available: {', '.join(scenarios.NETWORKS)}",
        )
    return net


@app.get("/api/networks/{network_id}/graph", response_model=NetworkGraph, tags=["network"])
def get_network_graph(network_id: str) -> NetworkGraph:
    """The full weighted directed graph: every node, and every ordered pair of
    nodes as a road with distance, travel time and congestion.

    This is the optimizer's input.
    """
    graph = scenarios.get_graph(network_id)
    if graph is None:
        raise HTTPException(
            status_code=404,
            detail=f"No network '{network_id}'. Available: {', '.join(scenarios.NETWORKS)}",
        )
    return graph


@app.post("/api/networks/validate", response_model=ValidationResult, tags=["network"])
def validate(net: Network) -> ValidationResult:
    """Check an uploaded network and explain anything wrong with it.

    Returns 200 with `valid: false` rather than an error status - an invalid
    network is a normal answer to this question, not a server failure.
    """
    return validate_network(net)


# ---------------------------------------------------------------------------
# Solving
#
# A solve is a job, not a request. The browser starts one, polls it, then
# collects the result. See app/jobs.py for why.
# ---------------------------------------------------------------------------


class WeightsIn(BaseModel):
    """Objective weights. Defaults match app/optimizer/fitness.py."""

    time: float = Field(1.0, ge=0)
    distance: float = Field(0.5, ge=0)
    congestion: float = Field(0.3, ge=0)
    vehicle: float = Field(15.0, ge=0)


class SolveRequest(BaseModel):
    network_id: str
    algorithm: Literal["qpso", "pso", "both"] = "qpso"
    particles: int = Field(40, ge=2, le=300)
    iterations: int = Field(500, ge=1, le=5000)
    seed: int = 42
    weights: WeightsIn = WeightsIn()
    # Defaults are the tuned values from the Phase 3 sweep, not the published
    # ones - see Wiki/benchmark-results.md.
    alpha_start: float = Field(0.9, gt=0, le=2.0)
    alpha_end: float = Field(0.4, gt=0, le=2.0)
    inertia_start: float = Field(0.729, ge=0, le=1.5)
    inertia_end: float = Field(0.729, ge=0, le=1.5)
    # QPSO variants, both off by default so the API's default run is Sun's
    # algorithm. On ggn-50 the quadratic curve is worth about 2% - see
    # backend/validate.py.
    weighted_mbest: bool = False
    alpha_curve: Literal["linear", "quadratic"] = "linear"


class JobStarted(BaseModel):
    job_id: str


class JobStatus(BaseModel):
    job_id: str
    status: str
    algorithm: str
    phase: str
    iteration: int
    total_iterations: int
    progress: float
    best_cost: Optional[float] = None
    curve: List[float] = []
    error: Optional[str] = None


@app.post("/api/solve", response_model=JobStarted, tags=["solve"])
def solve(req: SolveRequest) -> JobStarted:
    """Start a solve. Returns immediately with a job id to poll."""
    graph = scenarios.get_graph(req.network_id)
    if graph is None:
        raise HTTPException(
            status_code=404,
            detail=f"No network '{req.network_id}'. Available: {', '.join(scenarios.NETWORKS)}",
        )
    if req.alpha_end > req.alpha_start:
        raise HTTPException(
            status_code=400,
            detail="Alpha must contract: the end value cannot exceed the start value.",
        )

    problem = Problem(graph)
    job = jobs.start(
        problem,
        network_id=req.network_id,
        algorithm=req.algorithm,
        particles=req.particles,
        iterations=req.iterations,
        seed=req.seed,
        weights=Weights(
            time=req.weights.time, distance=req.weights.distance,
            congestion=req.weights.congestion, vehicle=req.weights.vehicle,
        ),
        alpha=(req.alpha_start, req.alpha_end),
        inertia=(req.inertia_start, req.inertia_end),
        weighted_mbest=req.weighted_mbest,
        alpha_curve=req.alpha_curve,
    )
    return JobStarted(job_id=job.id)


@app.get("/api/jobs/{job_id}", response_model=JobStatus, tags=["solve"])
def job_status(job_id: str) -> JobStatus:
    """Poll a running solve. Cheap enough to call a few times a second."""
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail="No such job. Jobs are held in memory, so restarting the API clears them.",
        )
    return JobStatus(
        job_id=job.id, status=job.status, algorithm=job.algorithm, phase=job.phase,
        iteration=job.iteration, total_iterations=job.total_iterations,
        progress=round(job.progress, 4), best_cost=job.best_cost,
        curve=job.live_curve, error=job.error,
    )


@app.get("/api/jobs/{job_id}/result", tags=["solve"])
def job_result(job_id: str) -> dict:
    """The finished solve: routes ready to draw, totals, and convergence curves.

    Returned as a plain dict rather than a response_model because its shape is
    driven by which algorithms ran, and a model per shape would be more
    ceremony than the endpoint is worth.
    """
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="No such job.")
    if job.status == "failed":
        raise HTTPException(status_code=500, detail=job.error or "The solve failed.")
    if job.status != "done":
        raise HTTPException(
            status_code=409,
            detail=f"That solve is still {job.status}. Poll /api/jobs/{job_id} until it is done.",
        )

    graph = scenarios.get_graph(job.network_id)
    problem = Problem(graph)
    coords = {nd.id: [nd.lat, nd.lng] for nd in graph.nodes}
    depot = graph.nodes[0]

    exact_cost = None
    try:
        exact_cost = round(exact_optimum(problem, job.weights).cost, 2)
    except TooLargeForExact:
        pass  # expected on the 49-stop network

    def block(run: jobs.AlgorithmRun) -> dict:
        sol = run.best
        return {
            "algorithm": run.algorithm,
            "cost": round(sol.cost, 2),
            "startCost": round(run.start_cost, 2),
            "improvementPct": round(
                100.0 * (run.start_cost - sol.cost) / run.start_cost, 2
            ) if run.start_cost else 0.0,
            "totalTimeMin": round(sol.total_time_min, 1),
            "totalDistanceKm": round(sol.total_distance_km, 1),
            "congestionDelayMin": round(sol.congestion_delay_min, 1),
            "congestionSharePct": round(sol.congestion_share * 100, 1),
            "vehiclesUsed": sol.vehicles_used,
            "feasible": sol.feasible,
            "evaluations": run.evaluations,
            "elapsedS": round(run.elapsed_s, 3),
            "firstHitIteration": run.first_hit_iteration,
            "curve": [round(c, 3) for c in run.curve],
            "meanCurve": [round(c, 3) for c in run.mean_curve],
            "alphaCurve": [round(a, 4) for a in run.alpha_curve],
            "gapToExactPct": (
                None if exact_cost is None or exact_cost <= 0
                else round(100.0 * (sol.cost - exact_cost) / exact_cost, 2)
            ),
            "routes": jobs.routes_with_places(run, problem, coords),
        }

    return {
        "jobId": job.id,
        "network": {
            "id": problem.network_id, "name": problem.network_name,
            "customers": problem.customer_count, "vehicles": problem.vehicles,
            "capacity": problem.capacity, "totalDemand": problem.total_demand,
            "depot": {"name": depot.name, "at": [depot.lat, depot.lng]},
        },
        "setup": {
            "algorithm": job.algorithm, "particles": job.particles,
            "iterations": job.iterations, "seed": job.seed,
            "evaluations": job.particles * (job.iterations + 1),
            "alpha": list(job.alpha), "inertia": list(job.inertia),
            "weightedMbest": job.weighted_mbest, "alphaCurve": job.alpha_curve,
            "weights": {
                "time": job.weights.time, "distance": job.weights.distance,
                "congestion": job.weights.congestion, "vehicle": job.weights.vehicle,
            },
        },
        "exactCost": exact_cost,
        "results": {name: block(run) for name, run in job.runs.items()},
    }
