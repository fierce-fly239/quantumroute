#!/usr/bin/env python3
"""Render a solved network as a standalone HTML page.

    python3 report.py                       10-stop, with the exact optimum
    python3 report.py --network ggn-50       49-stop
    python3 report.py --open                 write it and open it

Phase 2's real deliverable is the command-line solver. This is that same result
made visible: routes drawn on a map, the convergence curve, and - where the
instance is small enough - the proven optimum next to what QPSO found.

Nothing here is part of the web app. The app gets wired to the optimizer in
Phase 4; this is a self-contained file you can open, mail, or drop in a deck.
"""

import argparse
import json
import webbrowser
from pathlib import Path
from typing import Dict, List, Optional

from app import scenarios
from app.optimizer.exact import TooLargeForExact, exact_optimum, subsets_required
from app.optimizer.fitness import Solution, Weights
from app.optimizer.problem import Problem
from app.optimizer.qpso import OptimizeResult, QPSOParams, optimize

# One colour per van. Chosen to stay distinguishable on a light grey basemap and
# to survive being printed in a deck.
# The depot's red (#d1442f) is deliberately not here: reusing it for a van made
# the depot indistinguishable from one of the routes on the map.
VAN_COLOURS = [
    "#2f7fd1", "#2e8b57", "#8a4fbd", "#c9820b", "#0e8f8f",
    "#b3376f", "#5a6b1f", "#3f5fa8", "#7a5c2e", "#4a4a8a",
]


def solution_payload(sol: Solution, problem: Problem, coords: Dict[str, List[float]]) -> dict:
    """Everything the page needs to draw one plan."""
    return {
        "cost": round(sol.cost, 2),
        "totalTime": round(sol.total_time_min, 1),
        "totalDistance": round(sol.total_distance_km, 1),
        "delay": round(sol.congestion_delay_min, 1),
        "delayShare": round(sol.congestion_share * 100, 1),
        "vehicles": sol.vehicles_used,
        "feasible": sol.feasible,
        "routes": [
            {
                "van": i + 1,
                "load": sol.loads[i],
                "distance": round(sol.route_distance_km[i], 1),
                "time": round(sol.route_time_min[i], 1),
                "stops": [problem.node_names[n] for n in route],
                "path": (
                    [coords[problem.node_ids[0]]]
                    + [coords[problem.node_ids[n]] for n in route]
                    + [coords[problem.node_ids[0]]]
                ),
            }
            for i, route in enumerate(sol.routes)
        ],
    }


def build_payload(network_id: str, params: QPSOParams, weights: Weights, want_exact: bool) -> dict:
    graph = scenarios.get_graph(network_id)
    if graph is None:
        raise SystemExit(f"No network '{network_id}'. Try: {', '.join(scenarios.NETWORKS)}")

    problem = Problem(graph)
    coords = {nd.id: [nd.lat, nd.lng] for nd in graph.nodes}

    result: OptimizeResult = optimize(problem, weights=weights, params=params)

    exact_block: Optional[dict] = None
    exact_note: Optional[str] = None
    if want_exact:
        try:
            best = exact_optimum(problem, weights)
            gap = 100.0 * (result.best.cost - best.cost) / best.cost if best.cost else 0.0
            exact_block = {
                "solution": solution_payload(best, problem, coords),
                "gapPct": round(gap, 2),
                "subsets": subsets_required(problem),
            }
        except TooLargeForExact as exc:
            exact_note = str(exc)

    depot = graph.nodes[0]
    return {
        "network": {
            "id": problem.network_id,
            "name": problem.network_name,
            "customers": problem.customer_count,
            "vehicles": problem.vehicles,
            "capacity": problem.capacity,
            "totalDemand": problem.total_demand,
            "fleetCapacity": problem.fleet_capacity,
            "loadPct": round(100.0 * problem.total_demand / problem.fleet_capacity, 0),
            "depot": {"name": depot.name, "at": [depot.lat, depot.lng]},
            "stops": [
                {"name": nd.name, "at": [nd.lat, nd.lng], "demand": nd.demand, "zone": nd.zone.value}
                for nd in graph.nodes[1:]
            ],
        },
        "run": {
            "particles": params.particles,
            "iterations": params.iterations,
            "seed": params.seed,
            "alphaStart": params.alpha_start,
            "alphaEnd": params.alpha_end,
            "evaluations": result.evaluations,
            "elapsed": round(result.elapsed_s, 3),
            "startCost": round(result.initial_cost, 2),
            "improvementPct": round(result.improvement_pct, 1),
            # The FIRST iteration that reached the final best cost. Using max()
            # here would report the last iteration of the run instead, which is
            # always the final iteration and says nothing.
            "lastImprovement": min(
                (r.iteration for r in result.history if r.best_cost <= result.best.cost),
                default=0,
            ),
            "history": [
                {"i": r.iteration, "best": round(r.best_cost, 2),
                 "mean": round(r.mean_cost, 2), "alpha": round(r.alpha, 4)}
                for r in result.history
            ],
        },
        "weights": {
            "time": weights.time, "distance": weights.distance,
            "congestion": weights.congestion, "vehicle": weights.vehicle,
        },
        "qpso": solution_payload(result.best, problem, coords),
        "exact": exact_block,
        "exactNote": exact_note,
    }


PAGE = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>QuantumRoute — __TITLE__</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
  :root{
    --ground:#f4f3ef; --surface:#fff; --surface-2:#faf9f6; --ink:#1a1a18;
    --muted:#5f5d57; --faint:#8b8880; --rule:#dedbd3; --accent:#0e6c7d;
    --green:#2c6b3e; --green-soft:#e3efe6; --amber:#8a5a10; --amber-soft:#f7eddb;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--ground);color:var(--ink);
    font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
    -webkit-font-smoothing:antialiased}
  .wrap{max-width:1000px;margin:0 auto;padding:0 22px 80px}
  header{padding:40px 0 22px;border-bottom:2px solid var(--ink)}
  h1{margin:0;font-size:34px;line-height:1.05;letter-spacing:-.02em}
  .sub{margin-top:10px;color:var(--muted);font-size:14px;
    font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
  h2{font-size:21px;margin:0 0 4px;letter-spacing:-.01em}
  section{margin-top:38px}
  .eyebrow{font:11px/1 ui-monospace,Menlo,monospace;letter-spacing:.14em;
    text-transform:uppercase;color:var(--faint);margin-bottom:9px}
  p{margin:0 0 12px;max-width:70ch;color:var(--muted)}
  p.lede{color:var(--ink)}
  .card{background:var(--surface);border:1px solid var(--rule);border-radius:11px;
    padding:20px 22px;box-shadow:0 1px 2px rgba(0,0,0,.04)}
  .stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(128px,1fr));gap:1px;
    background:var(--rule);border:1px solid var(--rule);border-radius:11px;overflow:hidden}
  .stat{background:var(--surface);padding:15px 16px}
  .stat .v{font-size:24px;font-weight:600;letter-spacing:-.02em;
    font-variant-numeric:tabular-nums;line-height:1.1}
  .stat .k{font:11px/1.3 ui-monospace,Menlo,monospace;letter-spacing:.07em;
    text-transform:uppercase;color:var(--faint);margin-top:6px}
  #map{height:520px;border-radius:11px;border:1px solid var(--rule);background:#e8e6e1}
  .legend{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
  .chip{display:inline-flex;align-items:center;gap:7px;background:var(--surface);
    border:1px solid var(--rule);border-radius:99px;padding:5px 12px 5px 8px;font-size:13px}
  .dot{width:11px;height:11px;border-radius:3px;flex-shrink:0}
  table{width:100%;border-collapse:collapse;font-size:14px}
  th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--rule);vertical-align:top}
  th{font:11px/1.3 ui-monospace,Menlo,monospace;letter-spacing:.08em;
    text-transform:uppercase;color:var(--faint);font-weight:500}
  td.n{font-variant-numeric:tabular-nums;white-space:nowrap}
  .stops{color:var(--muted);font-size:13.5px}
  .verdict{background:var(--green-soft);border:1px solid #bcd6c3;border-radius:11px;padding:20px 22px}
  .verdict .big{font-size:27px;font-weight:600;letter-spacing:-.02em;color:var(--green)}
  .note{background:var(--amber-soft);border:1px solid #e0cba2;border-radius:11px;padding:18px 20px}
  .note b{color:var(--amber)}
  .formula{background:var(--surface-2);border:1px solid var(--rule);border-radius:9px;
    padding:14px 16px;font:13.5px/1.9 ui-monospace,Menlo,monospace;
    overflow-x:auto;white-space:pre}
  footer{margin-top:44px;padding-top:18px;border-top:1px solid var(--rule);
    font:12px ui-monospace,Menlo,monospace;color:var(--faint)}
  .grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
  @media(max-width:760px){.grid2{grid-template-columns:1fr}}
  .leaflet-container{border-radius:11px}
</style>
</head><body>
<div class="wrap">

<header>
  <h1>QuantumRoute — <span id="netname"></span></h1>
  <div class="sub" id="runline"></div>
</header>

<section>
  <div class="eyebrow">What the optimizer produced</div>
  <div class="stats" id="stats"></div>
</section>

<section>
  <div class="eyebrow">The plan</div>
  <h2>Routes on the map</h2>
  <p>One colour per van. Every route starts and ends at the red depot. Lines are drawn
     stop to stop — they are the visiting order, not the turn-by-turn road geometry.</p>
  <div id="map"></div>
  <div class="legend" id="legend"></div>
</section>

<section>
  <div class="eyebrow">Per van</div>
  <table id="routes"><thead><tr>
    <th>Van</th><th>Load</th><th>Distance</th><th>Time</th><th>Stops in order</th>
  </tr></thead><tbody></tbody></table>
</section>

<section>
  <div class="eyebrow">How it got there</div>
  <h2>Convergence</h2>
  <p>Best cost found so far, at every iteration. Down is better. The line flattening
     means the swarm has contracted — <code>|mbest − x|</code> has shrunk and alpha is
     near its floor, so the jumps are too small to reach anywhere new.</p>
  <div class="card"><svg id="chart" viewBox="0 0 900 300" width="100%" height="300"
       preserveAspectRatio="none" role="img" aria-label="Convergence curve"></svg>
    <div id="chartlabels" style="display:flex;justify-content:space-between;
         font:11px ui-monospace,Menlo,monospace;color:var(--faint);margin-top:8px"></div>
  </div>
</section>

<section id="verifysec">
  <div class="eyebrow">Verification</div>
  <h2>Against the proven optimum</h2>
  <div id="verify"></div>
</section>

<section>
  <div class="eyebrow">How cost is computed</div>
  <h2>The score, in full</h2>
  <p>Four quantities in different units, converted to one number by a weight each.
     Lower wins. These are the actual figures from this run.</p>
  <div class="formula" id="formula"></div>
</section>

<footer id="foot"></footer>
</div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script id="payload" type="application/json">__DATA__</script>
<script>
(function(){
  var D = JSON.parse(document.getElementById('payload').textContent);
  var COLOURS = __COLOURS__;
  var net = D.network, run = D.run, q = D.qpso;

  document.getElementById('netname').textContent = net.name;
  document.getElementById('runline').textContent =
    net.customers + ' stops · ' + net.vehicles + ' vans × ' + net.capacity + ' units · ' +
    net.totalDemand + ' units of demand (' + net.loadPct + '% of fleet) · QPSO ' +
    run.particles + '×' + run.iterations + ', seed ' + run.seed;

  function stat(v, k){ return '<div class="stat"><div class="v">' + v +
    '</div><div class="k">' + k + '</div></div>'; }
  document.getElementById('stats').innerHTML =
    stat(q.cost, 'cost') + stat(q.totalTime + ' min', 'driving time') +
    stat(q.totalDistance + ' km', 'distance') +
    stat(q.delayShare + '%', 'time in traffic') +
    stat(q.vehicles, 'vans used') +
    stat(run.improvementPct + '%', 'better than start') +
    stat(run.elapsed + 's', 'solve time');

  // ---- map ----
  var map = L.map('map', {scrollWheelZoom:false});
  L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}',
    {attribution:'Tiles &copy; Esri', maxZoom:16}).addTo(map);
  L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}',
    {maxZoom:16}).addTo(map);

  var all = [];
  q.routes.forEach(function(r, i){
    var c = COLOURS[i % COLOURS.length];
    L.polyline(r.path, {color:c, weight:3.5, opacity:.85}).addTo(map);
    r.path.forEach(function(p){ all.push(p); });
    r.stops.forEach(function(name, k){
      var p = r.path[k+1];
      L.circleMarker(p, {radius:6, color:'#fff', weight:2, fillColor:c, fillOpacity:1})
        .addTo(map).bindPopup('<b>' + name + '</b><br>Van ' + r.van + ', stop ' + (k+1));
    });
  });
  L.circleMarker(net.depot.at, {radius:9, color:'#fff', weight:3,
    fillColor:'#d1442f', fillOpacity:1}).addTo(map)
    .bindPopup('<b>' + net.depot.name + '</b><br>Depot — every van starts and ends here');
  map.fitBounds(L.latLngBounds(all).pad(0.08));

  document.getElementById('legend').innerHTML =
    '<span class="chip"><span class="dot" style="background:#d1442f"></span>Depot</span>' +
    q.routes.map(function(r,i){
      return '<span class="chip"><span class="dot" style="background:' +
        COLOURS[i % COLOURS.length] + '"></span>Van ' + r.van + ' — ' +
        r.load + '/' + net.capacity + ' units</span>';
    }).join('');

  // ---- route table ----
  document.querySelector('#routes tbody').innerHTML = q.routes.map(function(r,i){
    return '<tr><td class="n"><span class="dot" style="display:inline-block;background:' +
      COLOURS[i % COLOURS.length] + ';margin-right:7px"></span>' + r.van + '</td>' +
      '<td class="n">' + r.load + '/' + net.capacity + '</td>' +
      '<td class="n">' + r.distance + ' km</td>' +
      '<td class="n">' + r.time + ' min</td>' +
      '<td class="stops">' + r.stops.join(' → ') + '</td></tr>';
  }).join('');

  // ---- convergence chart ----
  var h = run.history, W = 900, H = 300, pad = 8;
  var lo = Math.min.apply(null, h.map(function(r){return r.best;}));
  var hi = Math.max.apply(null, h.map(function(r){return r.best;}));
  var span = (hi - lo) || 1;
  function xy(r, i){
    return [pad + i / Math.max(1, h.length - 1) * (W - 2*pad),
            pad + (1 - (r.best - lo) / span) * (H - 2*pad)];
  }
  var pts = h.map(xy);
  var line = pts.map(function(p,i){ return (i?'L':'M') + p[0].toFixed(1) + ' ' + p[1].toFixed(1); }).join(' ');
  var area = line + ' L ' + (W-pad) + ' ' + (H-pad) + ' L ' + pad + ' ' + (H-pad) + ' Z';
  document.getElementById('chart').innerHTML =
    '<path d="' + area + '" fill="rgba(14,108,125,.10)"/>' +
    '<path d="' + line + '" fill="none" stroke="#0e6c7d" stroke-width="2.2" ' +
    'stroke-linejoin="round" vector-effect="non-scaling-stroke"/>';
  document.getElementById('chartlabels').innerHTML =
    '<span>iteration 0 — cost ' + run.startCost + '</span>' +
    '<span>last improvement: iteration ' + run.lastImprovement + '</span>' +
    '<span>iteration ' + (h.length-1) + ' — cost ' + q.cost + '</span>';

  // ---- verification ----
  var v = document.getElementById('verify');
  if (D.exact) {
    var e = D.exact;
    v.innerHTML = '<div class="verdict"><div class="big">QPSO came within ' +
      e.gapPct + '% of the best plan that exists.</div>' +
      '<p style="color:#2c6b3e;margin-top:8px">Proven optimum <b>' + e.solution.cost +
      '</b> · QPSO found <b>' + q.cost + '</b>. The optimum was computed by checking every ' +
      'one of ' + e.subsets.toLocaleString() + ' subsets of stops — possible only because ' +
      'this instance is small.</p></div>';
  } else {
    v.innerHTML = '<div class="note"><p style="color:inherit"><b>No proven optimum for this ' +
      'instance — and that is the point.</b></p><p style="color:inherit">' +
      (D.exactNote || '') + '</p></div>';
  }

  // ---- formula ----
  var w = D.weights;
  function row(label, val, wt){
    var prod = (val * wt);
    return '  ' + label.padEnd(22) + String(val).padStart(9) + '  × ' +
           String(wt).padStart(5) + '  = ' + prod.toFixed(2).padStart(9) + '\n';
  }
  document.getElementById('formula').textContent =
    row('minutes driven', q.totalTime, w.time) +
    row('kilometres driven', q.totalDistance, w.distance) +
    row('minutes in traffic', q.delay, w.congestion) +
    row('vans used', q.vehicles, w.vehicle) +
    '  ' + '-'.repeat(50) + '\n' +
    '  ' + 'cost'.padEnd(22) + ' '.repeat(27) + String(q.cost).padStart(9);

  document.getElementById('foot').textContent =
    'QuantumRoute · SIH26137 · ' + run.evaluations.toLocaleString() +
    ' plans evaluated in ' + run.elapsed + 's · alpha ' + run.alphaStart + ' → ' +
    run.alphaEnd + ' · seed ' + run.seed + ' (fixed, so this run repeats exactly)';
})();
</script>
</body></html>
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--network", default="ggn-10", choices=sorted(scenarios.NETWORKS))
    ap.add_argument("--particles", type=int, default=40)
    ap.add_argument("--iterations", type=int, default=500)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--no-exact", action="store_true", help="skip the proven optimum")
    ap.add_argument("--out", help="where to write the page")
    ap.add_argument("--open", action="store_true", help="open it in the browser")
    args = ap.parse_args()

    params = QPSOParams(particles=args.particles, iterations=args.iterations, seed=args.seed)
    payload = build_payload(args.network, params, Weights(), not args.no_exact)

    html = (
        PAGE.replace("__TITLE__", payload["network"]["name"])
        .replace("__DATA__", json.dumps(payload))
        .replace("__COLOURS__", json.dumps(VAN_COLOURS))
    )

    out = Path(args.out) if args.out else (
        Path(__file__).resolve().parent.parent / "reports" / f"{args.network}.html"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"Wrote {out}  ({out.stat().st_size // 1024} KB)")
    if args.open:
        webbrowser.open(out.as_uri())


if __name__ == "__main__":
    main()
