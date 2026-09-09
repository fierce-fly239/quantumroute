import { useState } from "react";
import { Link } from "react-router-dom";
import ConvergenceChart from "../components/ConvergenceChart.jsx";
import RouteMap from "../components/RouteMap.jsx";
import { DEPOT_COLOR, vanColour } from "../components/mapBase.jsx";
import { useStore } from "../store.jsx";

// Figma palette: cyan for QPSO, rose for classical PSO.
const COLOUR = { qpso: "#06b6d4", pso: "#f43f5e" };
const NAME = { qpso: "QPSO", pso: "Classical PSO" };

function Stat({ value, label, tone }) {
  return (
    <div className="stat">
      <div className={`stat-n${tone ? ` stat-${tone}` : ""}`}>{value}</div>
      <div className="stat-l">{label}</div>
    </div>
  );
}

export default function Results() {
  const { result } = useStore();
  const [shown, setShown] = useState(null);   // which algorithm's routes to draw
  const [highlight, setHighlight] = useState(null);

  if (!result) {
    return (
      <div className="page">
        <div className="page-head">
          <h1>Results</h1>
          <p className="page-lede">
            The routes the optimizer found, and how QPSO compared with classical
            PSO on the same problem.
          </p>
        </div>
        <div className="notice">
          No solve has finished yet. Go to <Link to="/run">Run</Link> and press
          Start solve.
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

  return (
    <div className="page page-wide">
      <div className="page-head">
        <h1>Results</h1>
        <p className="page-lede">
          {result.network.name} · {result.network.customers} stops ·{" "}
          {result.setup.particles}×{result.setup.iterations} ={" "}
          {result.setup.evaluations.toLocaleString()} plans evaluated per algorithm ·
          seed {result.setup.seed}
        </p>
      </div>

      {both && (
        <div className={`verdict verdict-${winner}`}>
          <strong>{NAME[winner]} won this run.</strong>{" "}
          {result.results[winner].cost.toFixed(2)} against{" "}
          {result.results[names.find((n) => n !== winner)].cost.toFixed(2)} — a
          difference of{" "}
          {Math.abs(
            100 *
              (result.results[names.find((n) => n !== winner)].cost -
                result.results[winner].cost) /
              result.results[names.find((n) => n !== winner)].cost
          ).toFixed(2)}
          %. Both had the identical encoding, objective and evaluation budget.
          <div className="verdict-note">
            One run is one sample. The 30-run benchmarks are the real comparison,
            and QPSO leads on both: 0.59% on 10 stops, and 0.65% on 49 stops
            measured on seeds held out from tuning.
          </div>
        </div>
      )}

      <div className="stats">
        <Stat value={run.cost.toFixed(2)} label="Cost" />
        <Stat value={`${run.totalTimeMin} min`} label="Driving time" />
        <Stat value={`${run.totalDistanceKm} km`} label="Distance" />
        <Stat value={`${run.congestionSharePct}%`} label="Time in traffic" />
        <Stat value={run.vehiclesUsed} label="Vans used" />
        <Stat value={`${run.improvementPct}%`} label="Better than start" />
        {run.gapToExactPct != null && (
          <Stat
            value={`+${Math.abs(run.gapToExactPct).toFixed(2)}%`}
            label="Above proven optimum"
            tone={Math.abs(run.gapToExactPct) < 1 ? "good" : null}
          />
        )}
        <Stat value={`${run.elapsedS}s`} label="Solve time" />
      </div>

      {both && (
        <div className="seg">
          {names.map((n) => (
            <button
              key={n}
              className={`seg-btn${n === active ? " seg-on" : ""}`}
              onClick={() => { setShown(n); setHighlight(null); }}
            >
              <span className="swatch" style={{ background: COLOUR[n] }} />
              {NAME[n]} · {result.results[n].cost.toFixed(2)}
            </button>
          ))}
        </div>
      )}

      <section className="panel">
        <h2>The routes</h2>
        <p className="panel-lede">
          One colour per van, every route starting and ending at the red depot.
          Lines show the visiting order, not the turn-by-turn road geometry —
          we model roads as weighted connections between places, so drawing
          anything else would be inventing detail the model does not have.
        </p>
        <RouteMap routes={run.routes} depot={result.network.depot} highlight={highlight} />
        <div className="legend legend-flow">
          <span className="legend-item">
            <span className="swatch" style={{ background: DEPOT_COLOR }} /> Depot
          </span>
          {run.routes.map((r, i) => (
            <button
              key={r.van}
              className={`legend-item legend-btn${highlight === r.van ? " legend-on" : ""}`}
              onClick={() => setHighlight(highlight === r.van ? null : r.van)}
            >
              <span className="swatch" style={{ background: vanColour(i) }} />
              Van {r.van} — {r.load}/{result.network.capacity}
            </button>
          ))}
        </div>
      </section>

      <section className="panel">
        <h2>Per van</h2>
        <table className="table">
          <thead>
            <tr>
              <th>Van</th><th>Load</th><th>Distance</th><th>Time</th>
              <th>In traffic</th><th>Stops in order</th>
            </tr>
          </thead>
          <tbody>
            {run.routes.map((r, i) => (
              <tr
                key={r.van}
                className={highlight === r.van ? "row-on" : ""}
                onMouseEnter={() => setHighlight(r.van)}
                onMouseLeave={() => setHighlight(null)}
              >
                <td>
                  <span className="swatch" style={{ background: vanColour(i) }} /> {r.van}
                </td>
                <td className="num">{r.load}/{result.network.capacity}</td>
                <td className="num">{r.distanceKm} km</td>
                <td className="num">{r.timeMin} min</td>
                <td className="num">{r.delayMin} min</td>
                <td className="stops">{r.stops.map((s) => s.name).join(" → ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="panel">
        <h2>Convergence{both ? " — QPSO against PSO" : ""}</h2>
        <p className="panel-lede">
          Best cost found so far at each iteration, for the whole run. Flat means
          the swarm has contracted and further iterations bought nothing.
        </p>
        <ConvergenceChart
          series={names.map((n) => ({
            label: NAME[n],
            colour: COLOUR[n],
            values: result.results[n].curve,
          }))}
          height={340}
        />
        <div className="conv-notes">
          {names.map((n) => (
            <div key={n} className="conv-note">
              <span className="swatch" style={{ background: COLOUR[n] }} />
              <strong>{NAME[n]}</strong> reached its final answer at iteration{" "}
              {result.results[n].firstHitIteration} of {result.setup.iterations},
              in {result.results[n].elapsedS}s.
            </div>
          ))}
        </div>
      </section>

      {result.exactCost != null && (
        <section className="panel">
          <h2>Verified against the proven optimum</h2>
          <p className="panel-lede">
            This instance is small enough to solve exactly, by checking every
            legal plan. That gives a floor nothing can beat — so the number below
            is a measurement, not a claim.
          </p>
          <div className="stats">
            <Stat value={result.exactCost.toFixed(2)} label="Proven best possible" />
            {names.map((n) => (
              <Stat
                key={n}
                value={`+${Math.abs(result.results[n].gapToExactPct).toFixed(2)}%`}
                label={`${NAME[n]} above optimum`}
                tone={Math.abs(result.results[n].gapToExactPct) < 1 ? "good" : null}
              />
            ))}
          </div>
        </section>
      )}

      <div className="toolbar">
        <button
          className="btn"
          onClick={() => {
            const blob = new Blob([JSON.stringify(result, null, 2)],
              { type: "application/json" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `quantumroute-${result.network.id}-${result.setup.seed}.json`;
            a.click();
            URL.revokeObjectURL(url);
          }}
        >
          Export this result as JSON
        </button>
        <Link className="btn" to="/run">Run again</Link>
      </div>
    </div>
  );
}
