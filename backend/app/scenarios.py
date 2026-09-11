"""Built-in delivery networks.

Gurugram is the demo city: the internal round is at the Vedam GGN campus, it is a
real logistics hub for Delhi NCR, and its congestion is the problem this project
is about. Bengaluru is kept as a second city so scalability can be shown across
more than one network.

Coordinates are approximate real positions of real places, accurate enough to sit
correctly on a map. Demands and the traffic model are simulated - the problem
statement explicitly allows "real-time or simulated traffic conditions", and
simulated data is in fact required for the Phase 3 benchmark, because QPSO and PSO
have to be compared on an identical, unchanging problem.
"""

# `X | None` in an annotation is evaluated at def-time before Python 3.10, and
# macOS still ships 3.9 - which made this module fail to import on a stock Mac.
# This turns every annotation in the file into a string, so the syntax is fine
# on 3.9 while staying exactly as readable.
from __future__ import annotations

import random
from typing import Dict, List, Tuple

from .geo import build_edges
from .models import Fleet, Network, NetworkGraph, NetworkMeta, Node, NodeType, Zone

# name, lat, lng, zone
GURUGRAM_PLACES: List[Tuple[str, float, float, Zone]] = [
    ("DLF Cyber Hub", 28.4950, 77.0890, Zone.CYBER_CITY),
    ("Ambience Mall", 28.5045, 77.0975, Zone.CYBER_CITY),
    ("DLF Phase 3", 28.4930, 77.0980, Zone.CYBER_CITY),
    ("Unitech Cyber Park", 28.5010, 77.0930, Zone.CYBER_CITY),
    ("MG Road Metro", 28.4795, 77.0805, Zone.OLD_CITY),
    ("IFFCO Chowk", 28.4726, 77.0725, Zone.OLD_CITY),
    ("Huda City Centre", 28.4595, 77.0725, Zone.OLD_CITY),
    ("Sector 29 Leisure Valley", 28.4670, 77.0640, Zone.OLD_CITY),
    ("Sector 14 Market", 28.4680, 77.0400, Zone.OLD_CITY),
    ("Signature Tower", 28.4600, 77.0500, Zone.OLD_CITY),
    ("Medanta Medicity", 28.4390, 77.0400, Zone.OLD_CITY),
    ("Sadar Bazaar", 28.4620, 77.0290, Zone.OLD_CITY),
    ("Galleria Market", 28.4680, 77.0900, Zone.GOLF_COURSE),
    ("Sushant Lok Phase 1", 28.4670, 77.0840, Zone.GOLF_COURSE),
    ("Golf Course Road Sector 54", 28.4420, 77.1025, Zone.GOLF_COURSE),
    ("Sector 56", 28.4210, 77.1060, Zone.GOLF_COURSE),
    ("Golf Course Ext Sector 62", 28.4090, 77.0700, Zone.GOLF_COURSE),
    ("Vatika Chowk Sohna Road", 28.4089, 77.0400, Zone.SOHNA_ROAD),
    ("Subhash Chowk", 28.4230, 77.0370, Zone.SOHNA_ROAD),
    ("Badshahpur", 28.3930, 77.0400, Zone.SOHNA_ROAD),
    ("Sector 49 Sohna Road", 28.4180, 77.0490, Zone.SOHNA_ROAD),
    ("Rajiv Chowk", 28.4290, 77.0400, Zone.HIGHWAY),
    ("Kherki Daula Toll", 28.4180, 76.9880, Zone.HIGHWAY),
    ("Dwarka Expressway Sector 102", 28.5100, 76.9900, Zone.HIGHWAY),
    ("Hero Honda Chowk", 28.4430, 77.0140, Zone.HIGHWAY),
    ("IMT Manesar", 28.3670, 76.9370, Zone.INDUSTRIAL),
    ("Udyog Vihar Phase V", 28.5060, 77.0900, Zone.INDUSTRIAL),
    ("Palam Vihar", 28.5090, 77.0330, Zone.INDUSTRIAL),
    ("Sector 37 Industrial", 28.4350, 76.9950, Zone.INDUSTRIAL),
]

GURUGRAM_DEPOT = ("Central Depot, Udyog Vihar Phase IV", 28.5030, 77.0860, Zone.INDUSTRIAL)

BENGALURU_PLACES: List[Tuple[str, float, float, Zone]] = [
    ("MG Road", 12.9756, 77.6068, Zone.OLD_CITY),
    ("Indiranagar 100ft Road", 12.9719, 77.6412, Zone.OLD_CITY),
    ("Koramangala 5th Block", 12.9345, 77.6265, Zone.OLD_CITY),
    ("Electronic City Phase 1", 12.8452, 77.6602, Zone.INDUSTRIAL),
    ("Whitefield ITPL", 12.9856, 77.7365, Zone.CYBER_CITY),
    ("Manyata Tech Park", 13.0450, 77.6205, Zone.CYBER_CITY),
    ("Silk Board Junction", 12.9172, 77.6229, Zone.HIGHWAY),
    ("Hebbal Flyover", 13.0358, 77.5970, Zone.HIGHWAY),
    ("Jayanagar 4th Block", 12.9250, 77.5938, Zone.OLD_CITY),
]
BENGALURU_DEPOT = ("Peenya Industrial Depot", 13.0280, 77.5190, Zone.INDUSTRIAL)

# Gurugram's sector grid, used to fill out the large network beyond the named
# landmarks. Real city, real layout - Gurugram genuinely is numbered sectors.
GURUGRAM_BOUNDS = (28.375, 28.515, 76.960, 77.105)  # lat_min, lat_max, lng_min, lng_max
SECTOR_ZONES = [Zone.OLD_CITY, Zone.SOHNA_ROAD, Zone.GOLF_COURSE, Zone.INDUSTRIAL]


def _make_nodes(
    depot: Tuple[str, float, float, Zone],
    places: List[Tuple[str, float, float, Zone]],
    count: int,
    seed: int,
    fill_sectors: bool = False,
) -> List[Node]:
    """Build `count` nodes: one depot plus (count - 1) customers.

    Seeded, so the same scenario always produces the same demands. That matters:
    an unrepeatable problem cannot be used for a fair benchmark.
    """
    rng = random.Random(seed)
    nodes: List[Node] = [
        Node(
            id="depot",
            name=depot[0],
            type=NodeType.DEPOT,
            lat=depot[1],
            lng=depot[2],
            demand=0,
            zone=depot[3],
        )
    ]

    chosen = list(places[: count - 1])

    if fill_sectors:
        lat_min, lat_max, lng_min, lng_max = GURUGRAM_BOUNDS
        used = {p[0] for p in chosen}
        sector_no = 1
        while len(chosen) < count - 1:
            while f"Sector {sector_no}" in used:
                sector_no += 1
            chosen.append(
                (
                    f"Sector {sector_no}",
                    round(rng.uniform(lat_min, lat_max), 5),
                    round(rng.uniform(lng_min, lng_max), 5),
                    rng.choice(SECTOR_ZONES),
                )
            )
            used.add(f"Sector {sector_no}")
            sector_no += 1

    for i, (name, lat, lng, zone) in enumerate(chosen, start=1):
        nodes.append(
            Node(
                id=f"c{i:02d}",
                name=name,
                type=NodeType.CUSTOMER,
                lat=lat,
                lng=lng,
                demand=rng.randint(5, 20),
                zone=zone,
            )
        )
    return nodes


def _meta(net_id: str, name: str, city: str, desc: str, nodes: List[Node], fleet: Fleet) -> NetworkMeta:
    customers = [n for n in nodes if n.type == NodeType.CUSTOMER]
    return NetworkMeta(
        id=net_id,
        name=name,
        city=city,
        description=desc,
        node_count=len(nodes),
        customer_count=len(customers),
        fleet=fleet,
        total_demand=sum(n.demand for n in customers),
    )


def _build() -> Dict[str, Network]:
    out: Dict[str, Network] = {}

    ggn10 = _make_nodes(GURUGRAM_DEPOT, GURUGRAM_PLACES, 10, seed=2026)
    out["ggn-10"] = Network(
        meta=_meta(
            "ggn-10", "Gurugram - 10 stops", "Gurugram",
            "Nine deliveries across Cyber City, MG Road and Sohna Road from a "
            "depot in Udyog Vihar. Small enough to check the optimizer's answer by eye.",
            ggn10, Fleet(vehicles=3, capacity=50),
        ),
        nodes=ggn10,
    )

    ggn50 = _make_nodes(GURUGRAM_DEPOT, GURUGRAM_PLACES, 50, seed=7, fill_sectors=True)
    out["ggn-50"] = Network(
        meta=_meta(
            "ggn-50", "Gurugram - 50 stops", "Gurugram",
            "Forty-nine deliveries across the whole city, named landmarks plus the "
            "sector grid. The scale the problem statement is actually about.",
            ggn50, Fleet(vehicles=9, capacity=90),
        ),
        nodes=ggn50,
    )

    blr10 = _make_nodes(BENGALURU_DEPOT, BENGALURU_PLACES, 10, seed=99)
    out["blr-10"] = Network(
        meta=_meta(
            "blr-10", "Bengaluru - 10 stops", "Bengaluru",
            "A second city, to show the model is not tuned to one road network.",
            blr10, Fleet(vehicles=3, capacity=50),
        ),
        nodes=blr10,
    )
    return out


NETWORKS: Dict[str, Network] = _build()


def get_network(net_id: str) -> Network | None:
    return NETWORKS.get(net_id)


def get_graph(net_id: str) -> NetworkGraph | None:
    """Network plus its complete directed edge set."""
    net = NETWORKS.get(net_id)
    if net is None:
        return None
    return NetworkGraph(meta=net.meta, nodes=net.nodes, edges=build_edges(net.nodes))
