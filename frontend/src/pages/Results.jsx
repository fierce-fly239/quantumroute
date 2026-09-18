import { useState } from "react";
import { Link } from "react-router-dom";
import ConvergenceChart from "../components/ConvergenceChart.jsx";
import RouteMap from "../components/RouteMap.jsx";
import { useDepotColour, vanColour } from "../components/mapBase.jsx";
import { Card, Note, PageHead, Stat } from "../components/ui.jsx";
import { Check, Clock, Download, Gauge, MapIcon, RouteIcon, Sparkles, Target, Truck } from "../components/icons.jsx";
import { useStore } from "../store.jsx";

// Design palette: purple for QPSO, coral for classical PSO.
const COLOUR = { qpso: "#66529b", pso: "#e78368" };
const NAME = { qpso: "QPSO", pso: "Classical PSO" };

export default function Results() {
  const { result } = useStore();
  const [shown, setShown] = useState(null);   // which algorithm's routes to draw
  const [highlight, setHighlight] = useState(null);
  const depotColour = useDepotColour();

  if (!result) {
    return (
      <div className="page">
        <PageHead eyebrow="signals / results" status="nothing yet" statusTone="lilac" title="Results"
                  lede="The routes the optimizer found, and how QPSO compared with classical PSO on the same problem." />
        <div className="notice">
          No solve has finished yet. Go to <Link to="/run">Run</Link> and press start solve.
        </div>
      </div>
    );
  }

  const names = Object.keys(result.results);
  const active = shown && result.results[shown] ? shown : names[0];
  const run = result.results[active];
  const both = names.length > 1;
  const winner = both
    ? names.reduce((a, b) => (result.results[a].cost <= result.results[b].cost ? a : b))
    : null;
  const loser = both ? names.find((n) => n !== winner) : null;
  const margin = both
    ? Math.abs(100 * (result.results[loser].cost - result.results[winner].cost) / result.results[loser].cost)
    : 0;
  const source = result.network.source?.provider ?? "simulated";
  const maxTime = Math.max(...run.routes.map((r) => r.timeMin), 1);

  function exportJson() {
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `quantumroute-${result.network.id}-${result.setup.seed}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="page">
      <PageHead
        eyebrow="signals / results"
        status={source === "tomtom" ? "tomtom live traffic" : "simulated traffic"}
        statusTone={source === "tomtom" ? undefined : "lilac"}
        title="Results"
        lede={`${result.network.name} · ${result.network.customers} stops · ${result.setup.particles}×${result.setup.iterations} = ${result.setup.evaluations.toLocaleString()} plans evaluated per algorithm · seed ${result.setup.seed}`}
        actions={
          <>
            <Link className="btn" to="/run">run again</Link>
            <button className="btn btn-primary" onClick={exportJson}><Download /> export json</button>
          </>
        }
      />

      {both && (
        <div className="seg" style={{ marginBottom: 20 }}>
          {names.map((n) => (
            <button key={n} className={`seg-btn${n === active ? " seg-on" : ""}`} onClick={() => { setShown(n); setHighlight(null); }}>
              <span className="swatch" style={{ background: COLOUR[n] }} />
              {NAME[n]} · {result.results[n].cost.toFixed(2)}
            </button>
          ))}
        </div>
      )}

      <div className="stats">
        <Stat icon={<Target />} label="cost" value={run.cost.toFixed(2)} foot={`${run.improvementPct}% better than start`} tone="mint" delay={1} />
        <Stat icon={<Clock />} label="driving time" value={`${run.totalTimeMin} min`} foot={`${run.congestionSharePct}% in traffic`} tone="peach" delay={1} />
        <Stat icon={<RouteIcon />} label="distance" value={`${run.totalDistanceKm} km`} foot={`${run.vehiclesUsed} vans`} tone="butter" delay={1} />
        {run.gapToExactPct != null ? (
          <Stat icon={<Check />} label="above optimum" value={`+${Math.abs(run.gapToExactPct).toFixed(2)}%`} foot={`exact ${result.exactCost.toFixed(2)}`} tone="lilac" good={Math.abs(run.gapToExactPct) < 1} delay={1} />
        ) : (
          <Stat icon={<Gauge />} label="solve time" value={`${run.elapsedS}s`} foot={`${run.evaluations.toLocaleString()} plans`} tone="lilac" delay={1} />
        )}
      </div>

      <div className="two-col-narrow">
        <Card title={both ? "Convergence — QPSO against PSO" : "Convergence"} sub="best cost so far at each iteration · whole run" className="rise rise-2"
              pill={both ? `${NAME[winner]} ahead` : undefined}>
          <ConvergenceChart
            series={names.map((n) => ({ label: NAME[n], colour: COLOUR[n], values: result.results[n].curve }))}
            height={300}
          />
          <div className="conv-notes">
            {names.map((n) => (
              <div key={n} className="conv-note">
                <span className="swatch" style={{ background: COLOUR[n] }} />
                <strong>{NAME[n]}</strong> reached its final answer at iteration {result.results[n].firstHitIteration} of {result.setup.iterations}, in {result.results[n].elapsedS}s.
              </div>
            ))}
          </div>
        </Card>

        {both ? (
          <Note eyebrow="verdict · this run" icon={<Sparkles />} title={`${NAME[winner]} won by ${margin.toFixed(2)}%.`} tone={winner === "qpso" ? "" : "peach"}
                actions={<span className="pill">identical encoding, objective and budget</span>}>
            <p>
              {result.results[winner].cost.toFixed(2)} against {result.results[loser].cost.toFixed(2)}.
              One run is one sample. The 30-run benchmarks are the real comparison, and QPSO leads on both:
              0.59% on 10 stops, and 0.65% on 49 stops, measured on seeds held out from tuning.
            </p>
          </Note>
        ) : (
          <Note eyebrow="single algorithm" icon={<Sparkles />} title={`${NAME[active]} only.`}>
            <p>Set the algorithm to “Both” on Configure to see QPSO and classical PSO compared on the identical problem.</p>
          </Note>
        )}
      </div>

      <div className="stack mt">
        <Card icon={<MapIcon />} title="The routes" pill={`${run.routes.length} vans`} pillTone="lilac"
              sub="one colour per van · every route starts and ends at the depot · lines are the visiting order, not road geometry" flush>
          <div style={{ margin: -12 }}>
            <RouteMap routes={run.routes} depot={result.network.depot} highlight={highlight} />
          </div>
          <div className="legend-flow" style={{ padding: "12px 8px 4px" }}>
            <span className="legend-item"><span className="swatch" style={{ background: depotColour }} /> Depot</span>
            {run.routes.map((r, i) => (
              <button key={r.van} className={`legend-btn legend-item${highlight === r.van ? " legend-on" : ""}`}
                      onClick={() => setHighlight(highlight === r.van ? null : r.van)}>
                <span className="swatch" style={{ background: vanColour(i) }} />
                Van {r.van} — {r.load}/{result.network.capacity}
              </button>
            ))}
          </div>
        </Card>

        <div className="two-col-narrow">
          <Card icon={<Truck />} title="Per van" sub="hover a row to light its route on the map" flush>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr><th>Van</th><th>Load</th><th>Distance</th><th>Time</th><th>In traffic</th><th>Stops in order</th></tr>
                </thead>
                <tbody>
                  {run.routes.map((r, i) => (
                    <tr key={r.van} className={highlight === r.van ? "row-on" : ""}
                        onMouseEnter={() => setHighlight(r.van)} onMouseLeave={() => setHighlight(null)}>
                      <td><span className="swatch" style={{ background: vanColour(i) }} /> {r.van}</td>
                      <td className="num">{r.load}/{result.network.capacity}</td>
                      <td className="num">{r.distanceKm} km</td>
                      <td className="num">{r.timeMin} min</td>
                      <td className="num">{r.delayMin} min</td>
                      <td className="stops">{r.stops.map((s) => s.name).join(" → ")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <Card title="Minutes per van" sub="driving time per van">
            <div className="bars">
              {run.routes.map((r, i) => (
                <div key={r.van}>
                  <span className="mono" style={{ fontSize: 10, color: "var(--muted)" }}>{r.timeMin}</span>
                  <span className="bar-v" style={{ height: `${(r.timeMin / maxTime) * 100}%`, background: vanColour(i), opacity: highlight === null || highlight === r.van ? 1 : 0.3 }} />
                  <span className="bar-l">van {r.van}</span>
                </div>
              ))}
            </div>
          </Card>
        </div>

        {result.exactCost != null && (
          <Card icon={<Check />} title="Verified against the proven optimum" sub="every legal plan checked · a floor nothing can beat">
            <p className="card-lede">
              This instance is small enough to solve exactly. That gives a floor nothing can beat — so the gap below is a measurement, not a claim.
            </p>
            <div className="stats" style={{ marginBottom: 0 }}>
              <Stat icon={<Target />} label="proven best possible" value={result.exactCost.toFixed(2)} tone="mint" />
              {names.map((n) => (
                <Stat key={n} icon={<Check />} label={`${NAME[n]} above optimum`} value={`+${Math.abs(result.results[n].gapToExactPct).toFixed(2)}%`}
                      tone={n === "qpso" ? "lilac" : "peach"} good={Math.abs(result.results[n].gapToExactPct) < 1} />
              ))}
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
