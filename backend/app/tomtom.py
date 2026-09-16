"""TomTom Matrix Routing v2: real road distances and live travel times.

One call per network, never per candidate route. The optimizer evaluates tens
of thousands of fleet plans per solve; each of those is a sum of matrix lookups.
This module fills the matrix, once, and turns it into the same `Edge` objects
the simulated model produces, so nothing downstream knows the difference.

Which endpoint:
  * up to 100 cells  -> synchronous, one request, answer in the response
  * anything larger  -> asynchronous: submit, poll, download. Live traffic on
                        the sync endpoint is capped at 100 cells; async takes
                        2,500 on the free plan - exactly a 50-node network.

Billing (TomTom's own rule): when both sides exceed 5, a request costs
max(origins, destinations) x 5 transactions. So 50x50 = 250, not 2,500.

Congestion: TomTom reports `travelTimeInSeconds` and, inside it,
`trafficDelayInSeconds`. Our Edge wants a multiplier on free-flow time, so
    congestion = travel / (travel - delay)
which is >= 1.0 by construction, and makes `Problem.delay` (time - time/cong)
recover TomTom's delay figure exactly.

Routing points: a scenario coordinate can land on a road segment TomTom cannot
route INTO (Huda City Centre does - every route to it fails, every route from it
works). The scenario coordinates are never changed, because the simulated
benchmark depends on them. Instead `find_routing_point` probes a ring of spots
within ~100 m for one that routes both ways, and the caller sends TomTom that
spot for that node only. Overrides are keyed by node id and kept on disk.

Uses only the standard library: no `requests`, nothing new to install.
"""

import gzip
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set, Tuple

from .models import Edge, Node

BASE = "https://api.tomtom.com/routing/matrix/2"
SYNC_CELL_LIMIT = 100
ASYNC_CELL_LIMIT = 2500
TIMEOUT_S = 60
POLL_EVERY_S = 1.0
POLL_FOR_S = 180

LatLng = Tuple[float, float]


class TomTomError(RuntimeError):
    pass


@dataclass
class MatrixResult:
    edges: List[Edge]
    cells: int
    failures: int
    transactions: int
    departure_time: Optional[str]     # ISO string as TomTom reports it, local to the road
    endpoint: str                     # "sync" or "async"
    failed_nodes: Set[str] = field(default_factory=set)  # node ids with any failed cell

    @property
    def complete(self) -> bool:
        return self.failures == 0


def transactions_for(origins: int, destinations: int) -> int:
    """TomTom's billing formula for one matrix request."""
    if origins > 5 and destinations > 5:
        return max(origins, destinations) * 5
    return origins * destinations


def _request(method: str, url: str, body: Optional[dict] = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            # The async result download refuses requests without this.
            "Accept-Encoding": "gzip",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            raw = resp.read()
            if resp.headers.get("Content-Encoding", "").lower() == "gzip":
                raw = gzip.decompress(raw)
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:400]
        if e.code in (401, 403):
            raise TomTomError("TomTom rejected the API key. Check TOMTOM_API_KEY in backend/.env.") from e
        if e.code == 429:
            raise TomTomError("TomTom rate limit hit. Wait a minute and try again.") from e
        raise TomTomError(f"TomTom returned HTTP {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise TomTomError(f"Could not reach TomTom: {e.reason}. Is the Mac online?") from e


def _options(depart_at: str) -> dict:
    return {"departAt": depart_at, "traffic": "live", "routeType": "fastest", "travelMode": "car"}


def _point(lat: float, lng: float) -> dict:
    return {"point": {"latitude": lat, "longitude": lng}}


def _body(nodes: Sequence[Node], depart_at: str, overrides: Dict[str, LatLng]) -> dict:
    points = []
    for n in nodes:
        lat, lng = overrides.get(n.id, (n.lat, n.lng))
        points.append(_point(lat, lng))
    return {"origins": points, "destinations": points, "options": _options(depart_at)}


def _fetch_sync(body: dict, key: str) -> dict:
    return _request("POST", f"{BASE}?key={key}", body)


def _fetch_async(body: dict, key: str) -> dict:
    submitted = _request("POST", f"{BASE}/async?key={key}", body)
    job_id = submitted.get("jobId")
    if not job_id:
        raise TomTomError(f"TomTom did not return a job id: {submitted}")

    deadline = time.time() + POLL_FOR_S
    while time.time() < deadline:
        status = _request("GET", f"{BASE}/async/{job_id}?key={key}")
        state = status.get("state", "")
        if state == "Completed":
            break
        if state in ("Failed", "Cancelled"):
            raise TomTomError(f"TomTom matrix job {job_id} ended as {state}.")
        time.sleep(POLL_EVERY_S)
    else:
        raise TomTomError(f"TomTom matrix job {job_id} did not finish within {POLL_FOR_S}s.")

    return _request("GET", f"{BASE}/async/{job_id}/result?key={key}")


def cells_to_edges(nodes: Sequence[Node], payload: dict) -> "tuple[List[Edge], int, Optional[str], Set[str]]":
    """Turn TomTom's cell list into Edges. Diagonal cells are skipped; failed
    cells are counted, skipped, and the nodes involved reported so the caller
    can repair them. Pure function - this is what the tests exercise."""
    edges: List[Edge] = []
    failures = 0
    failed_nodes: Set[str] = set()
    departure: Optional[str] = None

    for cell in payload.get("data", []):
        i, j = cell["originIndex"], cell["destinationIndex"]
        if i == j:
            continue
        summary = cell.get("routeSummary")
        if not summary:
            failures += 1
            failed_nodes.add(nodes[i].id)
            failed_nodes.add(nodes[j].id)
            continue
        length_m = summary["lengthInMeters"]
        travel_s = summary["travelTimeInSeconds"]
        delay_s = summary.get("trafficDelayInSeconds", 0)
        departure = departure or summary.get("departureTime")

        free_s = max(travel_s - delay_s, 1)
        cong = max(1.0, travel_s / free_s)
        edges.append(
            Edge(
                source=nodes[i].id,
                target=nodes[j].id,
                distance_km=round(length_m / 1000.0, 3),
                travel_time_min=round(travel_s / 60.0, 2),
                congestion=round(cong, 3),
            )
        )
    return edges, failures, departure, failed_nodes


def culprits(nodes: Sequence[Node], payload: dict) -> Set[str]:
    """Which nodes actually need a new routing point.

    A failed cell names two nodes, but usually only one is at fault: the one
    that fails against many partners. A node is a culprit if it fails as origin
    or as destination against at least two different partners, or if it is the
    only node in any failed cell that meets that bar."""
    n = len(nodes)
    as_src: Dict[int, Set[int]] = {}
    as_dst: Dict[int, Set[int]] = {}
    for cell in payload.get("data", []):
        i, j = cell["originIndex"], cell["destinationIndex"]
        if i == j or cell.get("routeSummary"):
            continue
        as_src.setdefault(i, set()).add(j)
        as_dst.setdefault(j, set()).add(i)
    bad = {k for k, v in as_src.items() if len(v) >= 2} | {k for k, v in as_dst.items() if len(v) >= 2}
    if not bad:  # isolated single-cell failures: blame both ends
        bad = set(as_src) | set(as_dst)
    return {nodes[k].id for k in bad if k < n}


def fetch_matrix(
    nodes: Sequence[Node], key: str, depart_at: str = "now",
    overrides: Optional[Dict[str, LatLng]] = None,
) -> MatrixResult:
    """Live travel times between every pair of `nodes`. One network, one call.
    Never raises on failed cells - check `.complete` and `.failed_nodes`."""
    if not key:
        raise TomTomError("No TomTom API key. Put TOMTOM_API_KEY=... in backend/.env.")
    n = len(nodes)
    cells = n * n
    if cells > ASYNC_CELL_LIMIT:
        raise TomTomError(
            f"{n} nodes is {cells} matrix cells; TomTom's plan allows {ASYNC_CELL_LIMIT}."
        )

    body = _body(nodes, depart_at, overrides or {})
    if cells <= SYNC_CELL_LIMIT:
        payload, endpoint = _fetch_sync(body, key), "sync"
    else:
        payload, endpoint = _fetch_async(body, key), "async"

    edges, failures, departure, _ = cells_to_edges(nodes, payload)
    return MatrixResult(
        edges=edges, cells=cells, failures=failures,
        transactions=transactions_for(n, n),
        departure_time=departure, endpoint=endpoint,
        failed_nodes=culprits(nodes, payload) if failures else set(),
    )


# Ring of offsets to try, nearest first. 0.0005 deg is about 55 m; 0.001 about
# 110 m. Small enough that the stop is still the same place on the map.
_PROBE_RING: List[LatLng] = [
    (0.0005, 0), (-0.0005, 0), (0, 0.0005), (0, -0.0005),
    (0.001, 0), (-0.001, 0), (0, 0.001), (0, -0.001),
    (0.001, 0.001), (-0.001, -0.001), (0.001, -0.001), (-0.001, 0.001),
]


def find_routing_point(node: Node, partner: Node, key: str) -> "tuple[Optional[LatLng], int]":
    """A spot near `node` that TomTom can route to AND from, plus the number of
    probes it took. Each probe is a 2x2 sync matrix against `partner`
    (4 transactions). None if nothing in the ring works, in which case the
    scenario coordinate itself is the problem."""
    for probes, (dlat, dlng) in enumerate(_PROBE_RING, start=1):
        cand = (round(node.lat + dlat, 5), round(node.lng + dlng, 5))
        pts = [_point(partner.lat, partner.lng), _point(*cand)]
        payload = _fetch_sync({"origins": pts, "destinations": pts, "options": _options("now")}, key)
        ok = all(
            c.get("routeSummary") for c in payload.get("data", [])
            if c["originIndex"] != c["destinationIndex"]
        )
        if ok:
            return cand, probes
    return None, len(_PROBE_RING)
