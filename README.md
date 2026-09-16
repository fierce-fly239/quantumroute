# QuantumRoute Optimizer

Quantum-inspired vehicle route optimization for **SIH26137** (Smart India Hackathon 2026,
Egreen Quanta).

The app models a road network as a weighted graph and uses **Quantum Particle Swarm
Optimization (QPSO)** to find near-optimal delivery routes under traffic congestion, then
benchmarks the result against classical Particle Swarm Optimization.

> Nothing here runs on a quantum computer. QPSO is a classical algorithm that borrows the
> mathematics of quantum mechanics: instead of particles *walking* through the search space
> with a velocity, they are *sampled* from a probability distribution, which is what lets
> them escape a local optimum that plain PSO gets stuck in.

## Status

**Phase 1 — network modelling.** The road network is modelled, served and validated, and the
Network page draws it on a map. Three built-in scenarios ship with it. The optimizer arrives
in Phase 2; the other three pages are still placeholders. See
`../quantumroute_kb/Outputs/action-plan.md` for the full plan.

### Endpoints

| Endpoint | Returns |
|---|---|
| `GET /api/health` | Liveness, for the connection light |
| `GET /api/networks` | Summaries of every built-in scenario |
| `GET /api/networks/{id}` | One network's nodes — what the map draws |
| `GET /api/networks/{id}/graph` | Nodes **and** the full directed edge set — what the optimizer will consume |
| `POST /api/networks/validate` | Checks an uploaded network and explains anything wrong |

Nodes and edges are served separately on purpose: a 50-stop network has 2,450 edges and the
map needs none of them.

### The scenarios

| id | City | Stops | Fleet | Notes |
|---|---|---|---|---|
| `ggn-10` | Gurugram | 9 | 3 × 50 | Small enough to sanity-check the optimizer by eye |
| `ggn-50` | Gurugram | 49 | 9 × 90 | Named landmarks plus the sector grid |
| `blr-10` | Bengaluru | 9 | 3 × 50 | A second city, so the model isn't tuned to one road network |

### How traffic is modelled

Distances are great-circle, scaled by 1.35 because roads are not straight lines. Travel time
is distance over a 32 km/h free-flow city speed, multiplied by a congestion factor.

Congestion is derived from the **zone** each stop sits in (Cyber City, Golf Course Road, Old
City, Sohna Road, industrial, highway), and is **directed**: driving into Cyber City costs
more than driving out of it. That asymmetry is what makes this a directed graph rather than
an undirected one, which is what the problem statement asks for.

Demands and congestion are simulated, not live. The problem statement explicitly permits
*"real-time or simulated traffic conditions"* — and simulated data is in fact required for
the Phase 3 benchmark, because QPSO and PSO have to be compared on an identical, unchanging
problem. Everything is seeded, so the same scenario always produces the same numbers.

### Real traffic: the TomTom provider

Since 16 September the travel times can also come from **TomTom Matrix Routing v2**:
real road distances and live traffic, fetched once per network and frozen to a snapshot
in `backend/snapshots/`. Every solve after that reads the snapshot, so QPSO and PSO still
see the identical problem. The snapshot only changes on an explicit refresh.

- `backend/.env` holds `TOMTOM_API_KEY=...` (git-ignored). Get a key at developer.tomtom.com;
  no card, 2,500 free matrix transactions a month. A 50-stop network costs 250 per refresh.
- Default is still `simulated`. Set `QR_TRAVEL_PROVIDER=tomtom` in `.env` to switch the
  whole app, or pass `provider` per request: `GET /api/networks/ggn-50/graph?provider=tomtom`,
  `POST /api/solve` with `"provider": "tomtom"`.
- `GET /api/traffic` shows the default, whether a key is present, and each snapshot's age.
  `POST /api/networks/{id}/traffic/refresh` fetches live numbers now.
- Stops TomTom cannot route into at their exact coordinate (Huda City Centre is one) get a
  routing point within ~100 m, remembered in `snapshots/routing-points.json`. The scenario
  coordinates themselves are never edited: the benchmark depends on them.
- The bench, sweep and solve scripts always use the simulated model. Code: `app/tomtom.py`,
  `app/traffic.py`, `app/config.py`; tests in `tests/test_tomtom.py` run on a recorded
  response and never touch the network.

## Running it

```bash
./run.sh
```

That starts both halves and installs frontend packages on first run.

| | |
|---|---|
| App | http://localhost:5173 |
| API docs | http://127.0.0.1:8000/docs |

Ctrl-C stops both. If the header says **API not running**, the backend failed to start;
its errors print in the same terminal.

### Running them separately

```bash
cd backend && python3 -m uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend && npm run dev
```

## Requirements

- Python 3.11+ (this machine uses Homebrew Python 3.14)
- Node 20+

Backend packages: `pip3 install --user --break-system-packages -r backend/requirements.txt`

## Layout

```
backend/
  app/main.py         FastAPI app, CORS, /api/health
  requirements.txt
frontend/
  src/
    App.jsx           routes
    components/
      Nav.jsx         the four tabs
      BackendStatus.jsx   polls /api/health, shows the connection light
      Placeholder.jsx     "not built yet" block used by each page
    pages/            Network, Configure, Run, Results
    styles.css        design tokens, light and dark
  vite.config.js      proxies /api to the backend
run.sh                starts both
```

## The four pages

They are not arbitrary. Each maps onto a component SIH26137 names as required:

| Page | Covers | Lands |
|---|---|---|
| **Network** | Graph-based network modelling | Phase 1 |
| **Configure** | Constraint handling and objective weights | Phase 4 |
| **Run** | Convergence analysis | Phase 4 |
| **Results** | Routes plus systematic benchmarking | Phase 4 |

## How the two halves talk

The frontend never calls `http://localhost:8000` directly. It requests `/api/...` from its
own origin, and Vite proxies that to the backend (`vite.config.js`). One origin in
development means no CORS problems in the browser. CORS is configured on the backend anyway,
so the app still works if the two are ever served separately.

The connection light in the header polls `/api/health` every 10 seconds. It is the fastest
way to tell "backend is down" apart from "frontend is broken".

## Phase 2 — the optimizer

QPSO solves a network from the command line. No server, no browser.

```bash
cd backend
python3 solve.py                                    # 10-stop Gurugram
python3 solve.py --exact                            # and the proven optimum
python3 solve.py --network ggn-50 --particles 80 --iterations 1000
python3 solve.py --json run.json                    # save the full result
python3 solve.py --help                             # every option
```

`--exact` computes the genuinely optimal plan by dynamic programming and reports
how far QPSO fell short. It works up to 15 stops and refuses beyond that, which
is the point: at 49 stops there are 2^49 subsets to check. That refusal is what
NP-hardness looks like from the inside, and it is why a metaheuristic is the
right tool for the real instance.

### The code

| File | What it does |
|---|---|
| `app/optimizer/problem.py` | Network to flat matrices the search can hammer |
| `app/optimizer/encoding.py` | Random keys to delivery routes, and back |
| `app/optimizer/fitness.py`  | Route plan to one number: how bad it is |
| `app/optimizer/qpso.py`     | Sun's QPSO, the three equations |
| `app/optimizer/exact.py`    | The provable optimum, for small instances |
| `solve.py`                  | The command line |

### Tests

```bash
cd backend
python3 tests/run_tests.py
```

43 tests, no dependencies. Homebrew's Python refuses `pip install pytest` outside
a virtualenv, so the runner is hand-rolled — but the test files are ordinary
pytest-style functions, so `pytest` runs them unchanged if anyone sets one up.

## Running the optimizer

```bash
./run.sh                       # API on :8000, app on :5173
```

Then in the browser: **Configure** → **Run** → **Results**.
Or skip straight to a finished answer: <http://localhost:5173/run?demo=1>

From the command line, with no browser involved:

```bash
cd backend
python3 solve.py --exact                  # solve 10 stops, verify against the true optimum
python3 solve.py --network ggn-50         # solve 49 stops
python3 bench.py --network ggn-10 --runs 30 --report    # QPSO vs PSO, 30 paired runs
python3 sweep.py --network ggn-50         # find each algorithm's best settings
python3 tests/run_tests.py                # 73 tests, no dependencies
```
