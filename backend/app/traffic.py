"""Where a network's travel times come from.

Two providers:

  simulated  the zone model in geo.py. Deterministic, identical on every run.
             This is the benchmark instance: the 30 paired QPSO-vs-PSO runs need
             a problem that does not move, and every number in the deck was
             measured on it. Default.

  tomtom     real road distances and live traffic from TomTom, fetched once per
             network and FROZEN to disk as a snapshot. Every solve after that
             reads the snapshot, so QPSO and PSO still see the identical problem.
             The snapshot only changes when someone asks for a refresh.

`scenarios.get_graph` stays simulated forever; the benchmark and sweep scripts
call it directly and must not drift. The web API goes through `graph_for` here.
"""

import json
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

from . import config, scenarios, tomtom
from .models import Edge, EdgeSource, NetworkGraph

PROVIDERS = ("simulated", "tomtom")


def _snapshot_path(net_id: str):
    return config.SNAPSHOT_DIR / f"{net_id}.tomtom.json"


def _overrides_path():
    return config.SNAPSHOT_DIR / "routing-points.json"


def load_overrides() -> Dict[str, Dict[str, "tuple[float, float]"]]:
    """{net_id: {node_id: (lat, lng)}} - spots TomTom is given instead of the
    scenario coordinate, for the few stops it cannot route to. See tomtom.py."""
    path = _overrides_path()
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text())
    return {net: {nid: tuple(ll) for nid, ll in nodes.items()} for net, nodes in raw.items()}


def _save_overrides(all_overrides: Dict[str, Dict[str, "tuple[float, float]"]]) -> None:
    config.SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    _overrides_path().write_text(json.dumps(all_overrides, indent=1))


def snapshot_info(net_id: str) -> Optional[EdgeSource]:
    path = _snapshot_path(net_id)
    if not path.is_file():
        return None
    raw = json.loads(path.read_text())
    return EdgeSource(**raw["source"])


def _load_snapshot(net_id: str) -> Optional["tuple[EdgeSource, List[Edge]]"]:
    path = _snapshot_path(net_id)
    if not path.is_file():
        return None
    raw = json.loads(path.read_text())
    return EdgeSource(**raw["source"]), [Edge(**e) for e in raw["edges"]]


def refresh_snapshot(net_id: str) -> EdgeSource:
    """Ask TomTom now, freeze the answer. Raises tomtom.TomTomError on failure;
    the previous snapshot, if any, is left untouched in that case."""
    net = scenarios.get_network(net_id)
    if net is None:
        raise KeyError(net_id)

    key = config.tomtom_key()
    all_overrides = load_overrides()
    overrides = dict(all_overrides.get(net_id, {}))
    started = time.time()
    result = tomtom.fetch_matrix(net.nodes, key, overrides=overrides)
    transactions = result.transactions

    if not result.complete:
        # Some stop sits on a road TomTom cannot route to. Find a spot within
        # ~100 m that works, remember it, and fetch the matrix once more.
        by_id = {n.id: n for n in net.nodes}
        for nid in sorted(result.failed_nodes):
            node = by_id[nid]
            partner = next(n for n in net.nodes if n.id != nid)
            found, probes = tomtom.find_routing_point(node, partner, key)
            transactions += 4 * probes
            if found is None:
                raise tomtom.TomTomError(
                    f"TomTom cannot route to '{node.name}' from anywhere within 100 m "
                    f"of ({node.lat}, {node.lng}). That stop's coordinate needs checking."
                )
            overrides[nid] = found
        all_overrides[net_id] = overrides
        _save_overrides(all_overrides)
        result = tomtom.fetch_matrix(net.nodes, key, overrides=overrides)
        transactions += result.transactions
        if not result.complete:
            names = ", ".join(by_id[i].name for i in sorted(result.failed_nodes))
            raise tomtom.TomTomError(
                f"TomTom still cannot route {result.failures} roads after moving the "
                f"routing point for: {names}. Snapshot not saved."
            )

    source = EdgeSource(
        provider="tomtom",
        fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        departure_time=result.departure_time,
        cells=result.cells,
        transactions=transactions,
        endpoint=result.endpoint,
        fetch_seconds=round(time.time() - started, 2),
    )
    config.SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"source": source.model_dump(), "edges": [e.model_dump() for e in result.edges]}
    tmp = _snapshot_path(net_id).with_suffix(".tmp")
    tmp.write_text(json.dumps(payload))
    tmp.replace(_snapshot_path(net_id))
    return source


def graph_for(net_id: str, provider: Optional[str] = None) -> Optional[NetworkGraph]:
    """The graph the web app should solve. None if the network does not exist.

    With `tomtom`, a missing snapshot is fetched on first use; after that the
    frozen copy is served until `refresh_snapshot` is called."""
    provider = (provider or config.default_provider()).lower()
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown travel-time provider '{provider}'. Use one of {PROVIDERS}.")

    if provider == "simulated":
        graph = scenarios.get_graph(net_id)
        if graph is None:
            return None
        graph.source = EdgeSource(provider="simulated")
        return graph

    net = scenarios.get_network(net_id)
    if net is None:
        return None
    loaded = _load_snapshot(net_id)
    if loaded is None:
        refresh_snapshot(net_id)
        loaded = _load_snapshot(net_id)
    source, edges = loaded
    return NetworkGraph(meta=net.meta, nodes=net.nodes, edges=edges, source=source)


def status() -> Dict[str, object]:
    """What the /api/traffic endpoint reports."""
    return {
        "default_provider": config.default_provider(),
        "tomtom_key_present": bool(config.tomtom_key()),
        "snapshots": {
            net_id: (info.model_dump() if info else None)
            for net_id in scenarios.NETWORKS
            for info in [snapshot_info(net_id)]
        },
    }
