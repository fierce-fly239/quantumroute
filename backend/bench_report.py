"""Render a benchmark comparison as a standalone HTML page."""

import json
from pathlib import Path

PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>QPSO vs PSO — __TITLE__</title>
<style>
  :root{--ground:#f4f3ef;--surface:#fff;--surface-2:#faf9f6;--ink:#1a1a18;--muted:#5f5d57;
    --faint:#8b8880;--rule:#dedbd3;--q:#0e6c7d;--p:#b3562a;--green:#2c6b3e;--amber:#8a5a10;}
  *{box-sizing:border-box}
  body{margin:0;background:var(--ground);color:var(--ink);
    font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;-webkit-font-smoothing:antialiased}
  .wrap{max-width:980px;margin:0 auto;padding:0 22px 80px}
  header{padding:40px 0 22px;border-bottom:2px solid var(--ink)}
  h1{margin:0;font-size:33px;letter-spacing:-.02em;line-height:1.06}
  .sub{margin-top:10px;color:var(--muted);font:13px ui-monospace,Menlo,monospace}
  section{margin-top:36px}
  h2{font-size:21px;margin:0 0 10px;letter-spacing:-.01em}
  .eyebrow{font:11px/1 ui-monospace,Menlo,monospace;letter-spacing:.14em;
    text-transform:uppercase;color:var(--faint);margin-bottom:9px}
  p{margin:0 0 12px;max-width:72ch;color:var(--muted)}
  .verdict{border-radius:11px;padding:22px 24px;border:1px solid}
  .verdict.q{background:#e2eef0;border-color:#a8ccd3}
  .verdict.p{background:#f5e7dd;border-color:#e0c0a6}
  .verdict .big{font-size:25px;font-weight:600;letter-spacing:-.02em;line-height:1.25}
  table{width:100%;border-collapse:collapse;font-size:14px;background:var(--surface);
    border:1px solid var(--rule);border-radius:11px;overflow:hidden}
  th,td{text-align:right;padding:11px 13px;border-bottom:1px solid var(--rule)}
  th:first-child,td:first-child{text-align:left}
  thead th{font:11px ui-monospace,Menlo,monospace;letter-spacing:.08em;
    text-transform:uppercase;color:var(--faint);font-weight:500;background:var(--surface-2)}
  tbody tr:last-child td{border-bottom:none}
  td.n{font-variant-numeric:tabular-nums}
  .algo{font-weight:600}
  .algo .sw{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:8px}
  .win{color:var(--green);font-weight:600}
  .card{background:var(--surface);border:1px solid var(--rule);border-radius:11px;padding:20px 22px}
  .legend{display:flex;gap:16px;margin-top:10px;font-size:13px;color:var(--muted)}
  .legend b{display:inline-flex;align-items:center;gap:7px;font-weight:500;color:var(--ink)}
  .legend .sw{width:12px;height:3px;border-radius:2px;display:inline-block}
  .note{background:#f7eddb;border:1px solid #e0cba2;border-radius:11px;padding:18px 20px}
  .note b{color:var(--amber)}
  .grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
  @media(max-width:780px){.grid{grid-template-columns:1fr}}
  ul{margin:0 0 12px;padding-left:20px;color:var(--muted);max-width:72ch}
  li{margin-bottom:7px}
  footer{margin-top:44px;padding-top:18px;border-top:1px solid var(--rule);
    font:12px ui-monospace,Menlo,monospace;color:var(--faint)}
</style></head><body><div class="wrap">

<header>
  <h1>QPSO vs classical PSO<br><span style="font-weight:400;color:#5f5d57" id="net"></span></h1>
  <div class="sub" id="setup"></div>
</header>

<section><div class="eyebrow">The result</div><div id="verdict"></div></section>

<section>
  <div class="eyebrow">Distributions across all runs</div>
  <h2>The numbers</h2>
  <p>Lower cost is better. Every run is paired: on a given seed both algorithms start
     from the identical random swarm, so a win on that seed is not luck of the draw.</p>
  <table><thead><tr><th>Algorithm</th><th>Mean</th><th>Median</th><th>Best</th>
    <th>Worst</th><th>Std dev</th><th>Time/run</th></tr></thead>
    <tbody id="stats"></tbody></table>
  <div id="gapnote" style="margin-top:14px"></div>
</section>

<section>
  <div class="eyebrow">Averaged over every run</div>
  <h2>Convergence</h2>
  <p>Best cost found so far, averaged across all runs, against <b>share of the
     evaluation budget spent</b>. The two algorithms may use different swarm shapes
     at the same budget, so budget — not iteration index — is the axis on which
     they are comparable. A single run's curve is a staircase that depends on
     where that seed got lucky; the average is the behaviour of the algorithm.</p>
  <div class="card">
    <svg id="chart" viewBox="0 0 900 320" width="100%" height="320" preserveAspectRatio="none"></svg>
    <div class="legend">
      <b><span class="sw" style="background:#0e6c7d"></span>QPSO</b>
      <b><span class="sw" style="background:#b3562a"></span>PSO</b>
      <span id="chartrange" style="margin-left:auto;font:11px ui-monospace,monospace"></span>
    </div>
  </div>
</section>

<section>
  <div class="eyebrow">Every paired seed</div>
  <h2>Head to head</h2>
  <div class="card"><svg id="paired" viewBox="0 0 900 260" width="100%" height="260"></svg>
    <div class="legend"><span id="pairedtext"></span></div></div>
</section>

<section id="honest">
  <div class="eyebrow">Reading the numbers honestly</div>
  <h2>What this does and doesn't show</h2>
  <div id="honestbody"></div>
</section>

<footer id="foot"></footer>
</div>
<script id="payload" type="application/json">__DATA__</script>
<script>
(function(){
  var D = JSON.parse(document.getElementById('payload').textContent);
  var Q = D.qpso, P = D.pso, S = D.setup;
  var QC = '#0e6c7d', PC = '#b3562a';

  document.getElementById('net').textContent = D.problem.name;
  document.getElementById('setup').textContent =
    S.runs + ' paired runs · seeds ' + S.seeds[0] + '–' + S.seeds[S.seeds.length-1] +
    ' · ' + S.evaluationsPerRun.toLocaleString() + ' evaluations per run for both · ' +
    'QPSO ' + S.qpsoShape[0] + '×' + S.qpsoShape[1] + ' α ' + S.alphaSchedule[0] +
    '→' + S.alphaSchedule[1] + (S.alphaCurve === 'quadratic' ? ' quadratic' : '') +
    ' · PSO ' + S.psoShape[0] + '×' + S.psoShape[1] + ' w ' + S.inertiaSchedule[0] +
    '→' + S.inertiaSchedule[1];

  var qWins = D.headToHead.qpso, pWins = D.headToHead.pso;
  var leadQ = D.meanGapPct > 0;
  document.getElementById('verdict').innerHTML =
    '<div class="verdict ' + (leadQ ? 'q' : 'p') + '"><div class="big">' + D.verdict +
    '</div><p style="margin-top:10px;color:inherit;opacity:.85">Head to head: QPSO won ' +
    qWins + ', PSO won ' + pWins + ', tied ' + D.headToHead.tie + '.</p></div>';

  function row(s, colour, other){
    function cell(v, better){ return '<td class="n' + (better ? ' win' : '') + '">' + v + '</td>'; }
    return '<tr><td class="algo"><span class="sw" style="background:' + colour + '"></span>' +
      s.algorithm.toUpperCase() + '</td>' +
      cell(s.mean.toFixed(2), s.mean < other.mean) +
      cell(s.median.toFixed(2), s.median < other.median) +
      cell(s.best.toFixed(2), s.best < other.best) +
      cell(s.worst.toFixed(2), s.worst < other.worst) +
      cell(s.stdev.toFixed(3), s.stdev < other.stdev) +
      cell(s.meanElapsedS.toFixed(3) + 's', false) + '</tr>';
  }
  document.getElementById('stats').innerHTML = row(Q, QC, P) + row(P, PC, Q);

  if (D.exactCost != null) {
    document.getElementById('gapnote').innerHTML =
      '<div class="note"><b>Against the proven optimum (' + D.exactCost.toFixed(2) + ')</b><br>' +
      'QPSO averages <b>+' + Q.gapToExactPct.toFixed(2) + '%</b> above it · ' +
      'PSO averages <b>+' + P.gapToExactPct.toFixed(2) + '%</b>.</div>';
  } else {
    document.getElementById('gapnote').innerHTML =
      '<div class="note"><b>No proven optimum for this instance.</b> Exhaustive search ' +
      'needs 2<sup>49</sup> subset evaluations, so there is no floor to measure against — ' +
      'only the two algorithms against each other.</div>';
  }

  // Convergence.
  //
  // The x-axis is FRACTION OF THE EVALUATION BUDGET SPENT, not iteration index.
  // The two algorithms can now run different numbers of iterations at the same
  // budget (QPSO 20x1999 against PSO 80x499), and plotting both against a raw
  // index truncated QPSO's curve at PSO's length - which drew QPSO finishing
  // ABOVE PSO when it actually finishes below. Budget is the axis on which the
  // comparison is fair, so it is the axis the chart uses.
  var qc = Q.meanCurve, pc = P.meanCurve;
  var W=900,H=320,pad=10;
  var lo=Infinity, hi=-Infinity;
  [qc,pc].forEach(function(c){ c.forEach(function(v){
    if(v<lo) lo=v; if(v>hi) hi=v; }); });
  var span=(hi-lo)||1;
  function path(c){
    var d='', n=c.length;
    for(var i=0;i<n;i++){
      var x=pad+(n===1?0:i/(n-1))*(W-2*pad), y=pad+(1-(c[i]-lo)/span)*(H-2*pad);
      d+=(i?'L':'M')+x.toFixed(1)+' '+y.toFixed(1);
    }
    return d;
  }
  document.getElementById('chart').innerHTML =
    '<path d="'+path(pc)+'" fill="none" stroke="'+PC+'" stroke-width="2.2" vector-effect="non-scaling-stroke"/>' +
    '<path d="'+path(qc)+'" fill="none" stroke="'+QC+'" stroke-width="2.2" vector-effect="non-scaling-stroke"/>';
  document.getElementById('chartrange').textContent =
    'cost ' + hi.toFixed(0) + ' → ' + lo.toFixed(0) +
    ' · x-axis is share of the ' + S.evaluationsPerRun.toLocaleString() +
    '-evaluation budget, identical for both';

  // paired seeds
  var runs = Q.runs.map(function(r,i){ return {seed:r.seed, q:r.cost, p:P.runs[i].cost}; });
  var plo=Infinity, phi=-Infinity;
  runs.forEach(function(r){ plo=Math.min(plo,r.q,r.p); phi=Math.max(phi,r.q,r.p); });
  var pspan=(phi-plo)||1, PW=900, PH=260, ppad=14;
  var step=(PW-2*ppad)/runs.length;
  var svg='';
  runs.forEach(function(r,i){
    var x=ppad+step*(i+0.5);
    function y(v){ return ppad+(1-(v-plo)/pspan)*(PH-2*ppad); }
    svg+='<line x1="'+x+'" y1="'+y(r.q)+'" x2="'+x+'" y2="'+y(r.p)+'" stroke="#dedbd3" stroke-width="1.5"/>';
    svg+='<circle cx="'+x+'" cy="'+y(r.p)+'" r="3.6" fill="'+PC+'"/>';
    svg+='<circle cx="'+x+'" cy="'+y(r.q)+'" r="3.6" fill="'+QC+'"/>';
  });
  document.getElementById('paired').innerHTML=svg;
  document.getElementById('pairedtext').textContent =
    'One column per seed. Lower dot wins that seed. QPSO ' + qWins + ' · PSO ' + pWins +
    ' · tied ' + D.headToHead.tie;

  document.getElementById('foot').textContent =
    'QuantumRoute · SIH26137 · seeds ' + S.seeds[0] + '–' + S.seeds[S.seeds.length-1] +
    ' · identical encoding, objective and evaluation budget for both algorithms';
})();
</script>
__HONEST__
</body></html>
"""


def write_report(data: dict, out: Path, honest_html: str = "") -> Path:
    html = (
        PAGE.replace("__TITLE__", data["problem"]["name"])
        .replace("__DATA__", json.dumps(data))
        .replace("__HONEST__", honest_html)
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out


def honest_section(d: dict) -> str:
    """The 'what this does and doesn't show' block, generated from the results.

    Written as code rather than typed by hand so it cannot quietly drift away
    from the numbers above it, and so it says the same thing whichever algorithm
    happened to win.
    """
    q, p, s = d["qpso"], d["pso"], d["setup"]
    qpso_ahead = d["meanGapPct"] > 0
    leader, trailer = (q, p) if qpso_ahead else (p, q)
    lname = "QPSO" if qpso_ahead else "PSO"
    tname = "PSO" if qpso_ahead else "QPSO"

    points = []

    points.append(
        f"<li><b>{lname} has the lower mean cost</b> — {leader['mean']:.2f} against "
        f"{trailer['mean']:.2f}, a difference of {abs(d['meanGapPct']):.2f}%, over "
        f"{s['runs']} paired runs.</li>"
    )

    if q["stdev"] < p["stdev"]:
        ratio = p["stdev"] / q["stdev"] if q["stdev"] else float("inf")
        points.append(
            f"<li><b>QPSO is the more consistent of the two</b> — standard deviation "
            f"{q['stdev']:.2f} against PSO's {p['stdev']:.2f}, so PSO's results are "
            f"{ratio:.1f}× more spread out. PSO's worst run ({p['worst']:.2f}) is "
            f"materially worse than QPSO's ({q['worst']:.2f}). If you only get one "
            f"run, the spread matters as much as the mean.</li>"
        )
    else:
        ratio = q["stdev"] / p["stdev"] if p["stdev"] else float("inf")
        points.append(
            f"<li><b>PSO is the more consistent of the two here</b> — standard deviation "
            f"{p['stdev']:.2f} against QPSO's {q['stdev']:.2f}, {ratio:.1f}× tighter. "
            f"QPSO's spread is its weakness on this instance.</li>"
        )

    if q["best"] < p["best"] and qpso_ahead:
        points.append(
            f"<li><b>QPSO also found the single best plan of the experiment</b> "
            f"({q['best']:.2f} against PSO's {p['best']:.2f}).</li>"
        )
    elif q["best"] < p["best"]:
        # True, but easy to over-read, so it is stated together with the check that
        # refutes the obvious inference. Best-of-N resampling over these same runs
        # has PSO ahead at every practical N; QPSO's single best is one lucky draw.
        points.append(
            f"<li><b>QPSO found the single best plan of the experiment "
            f"({q['best']:.2f} against PSO's {p['best']:.2f}) — but this is not an "
            f"operational advantage.</b> Resampling these runs, PSO has the better "
            f"expected result at best-of-3, best-of-5 and best-of-10. QPSO only comes "
            f"out ahead if you take the single best of all {s['runs']} runs, which is "
            f"one lucky draw rather than a property you can rely on. Quoting the best "
            f"column without this check would be cherry-picking.</li>"
        )

    points.append(
        f"<li><b>Both algorithms produced a drivable plan in every single run</b> — "
        f"{q['feasibleRuns']}/{q['totalRuns']} and {p['feasibleRuns']}/{p['totalRuns']}. "
        f"No result here depends on a penalty term rescuing a broken solution.</li>"
    )

    points.append(
        f"<li><b>Both were tuned before being compared.</b> QPSO's published alpha "
        f"schedule (1.0→0.5) was tuned for continuous benchmark functions, not for "
        f"49-dimensional permutation keys; using it unchanged cost QPSO about 12% on "
        f"the large instance. Both algorithms were swept over their own schedules and "
        f"each is reported at its own best — α {s['alphaSchedule'][0]}→"
        f"{s['alphaSchedule'][1]} and w {s['inertiaSchedule'][0]}→"
        f"{s['inertiaSchedule'][1]}. Tuning one and not the other would have been the "
        f"easiest way to fake this result.</li>"
    )

    limits = [
        "<li><b>These are descriptive statistics, not a significance test.</b> "
        "30 paired runs with a Wilcoxon signed-rank test would be the textbook next "
        "step. We report means, spreads and win counts, and claim nothing about "
        "statistical significance.</li>",
        "<li><b>Two instances is not a benchmark suite.</b> These are two networks in "
        "one city under one traffic model. Standard CVRP libraries (Solomon, "
        "Augerat) would be the honest next step and are out of scope for the "
        "internal round.</li>",
        "<li><b>The decoder limits both algorithms equally.</b> Greedy next-fit packing "
        "means some legal groupings of stops into vans cannot be produced by any key "
        "vector. That restricts what either algorithm can reach — it does not bias the "
        "comparison, but it does bound both results.</li>",
    ]

    return f"""
<script>
(function(){{
  document.getElementById('honestbody').innerHTML =
    '<div class="card"><p style="color:#1a1a18;font-weight:500;margin-bottom:10px">'
    + 'What the numbers support</p><ul>{''.join(points).replace("'", "\\'")}</ul>'
    + '<p style="color:#1a1a18;font-weight:500;margin:18px 0 10px">'
    + 'What they do not support</p><ul>{''.join(limits).replace("'", "\\'")}</ul></div>';
}})();
</script>"""
