import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listNetworks } from "../api.js";
import { Card, Note, PageHead, Stat } from "../components/ui.jsx";
import { Cpu, Layers, RouteIcon, Sparkles, Target } from "../components/icons.jsx";
import { DEFAULT_CONFIG, useStore } from "../store.jsx";

/** Number input with a label and an explanation of what the number does.
 *  Every control here changes a result a judge might ask about, so none of them
 *  ship without a sentence saying what moving it means. */
function Field({ label, hint, children }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      <span className="field-hint">{hint}</span>
    </label>
  );
}

const TONES = ["mint", "lilac", "peach"];
const ALGO = { both: "QPSO + PSO", qpso: "QPSO", pso: "Classical PSO" };

export default function Configure() {
  const { config, update, updateWeight, reset } = useStore();
  const [scenarios, setScenarios] = useState([]);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    listNetworks().then(setScenarios).catch((e) => setError(e.message));
  }, []);

  const chosen = scenarios.find((s) => s.id === config.network_id);
  const evaluations = config.particles * (config.iterations + 1);
  const { provider: _p, ...cmp } = config;
  const { provider: _d, ...dflt } = DEFAULT_CONFIG;
  const dirty = JSON.stringify(cmp) !== JSON.stringify(dflt);

  return (
    <div className="page">
      <PageHead
        eyebrow="planning / configure"
        status={dirty ? "changed from defaults" : "tuned defaults"}
        statusTone={dirty ? "butter" : undefined}
        title="Configure"
        lede="Which algorithm to run, how hard to run it, and what counts as a good route. Every setting here changes the answer, so every one of them says what it does."
        actions={
          <button className="btn btn-primary" onClick={() => navigate("/run")}><Sparkles /> go to run</button>
        }
      />

      {error && <div className="notice notice-error">{error}</div>}

      <div className="stats stats-3">
        <Stat icon={<RouteIcon />} label="scenario" value={chosen ? `${chosen.customer_count} stops` : "—"} foot={chosen ? chosen.city : ""} tone="mint" delay={1} />
        <Stat icon={<Layers />} label="plans evaluated" value={evaluations.toLocaleString()} foot="per algorithm" tone="peach" delay={1} />
        <Stat icon={<Cpu />} label="algorithm" value={ALGO[config.algorithm]} foot={`seed ${config.seed}`} tone="lilac" delay={1} />
      </div>

      <div className="two-col-narrow">
        <Card title="Scenarios" sub="pick the network the solver works on" flush className="rise rise-2">
          <div className="rows">
            {scenarios.map((s, i) => {
              const on = s.id === config.network_id;
              return (
                <button key={s.id} className={`row${on ? " is-on" : ""}`} onClick={() => update({ network_id: s.id })}>
                  <span className={`row-badge tone-${TONES[i % TONES.length]}`}>{String(i + 1).padStart(2, "0")}</span>
                  <span className="row-main">
                    <span className="row-title">{s.name}</span>
                    <span className="row-sub">{s.customer_count} stops · {s.fleet.vehicles} vans × {s.fleet.capacity} · {s.total_demand} units</span>
                  </span>
                  <span className={`pill${on ? "" : " pill-lilac"}`}>{on ? "active" : "ready"}</span>
                </button>
              );
            })}
          </div>
        </Card>
        <Note eyebrow="why these defaults" icon={<Target />} title="Measured, not copied." tone="">
          <p>
            The defaults are the values our Phase 3 sweep found best on the 49-stop network.
            Sun's published alpha of 1.0 → 0.5 is miscalibrated for a permutation encoding
            and costs about 12%. Both algorithms always get the same evaluation budget.
          </p>
        </Note>
      </div>

      <div className="cfg-grid mt">
        <Card title="Problem" sub="what to solve, and with what">
          <Field
            label="Algorithm"
            hint="Both runs each in turn on the same problem — that comparison is objective 3 of the problem statement."
          >
            <select className="input" value={config.algorithm} onChange={(e) => update({ algorithm: e.target.value })}>
              <option value="both">Both — QPSO and classical PSO</option>
              <option value="qpso">QPSO only</option>
              <option value="pso">Classical PSO only</option>
            </select>
          </Field>
          <Field
            label="Seed"
            hint="Fixes the randomness. The same seed gives the same answer every time, which is what makes a demo repeatable and a benchmark fair."
          >
            <input type="number" className="input" value={config.seed} onChange={(e) => update({ seed: Number(e.target.value) })} />
          </Field>
          {chosen && (
            <p className="cfg-note">
              {chosen.customer_count} stops · {chosen.fleet.vehicles} vans × {chosen.fleet.capacity} units · {chosen.total_demand} units of demand
            </p>
          )}
        </Card>

        <Card title="Search effort" sub="how hard the swarm works">
          <Field
            label={`Particles: ${config.particles}`}
            hint="How many candidate solutions search at once. More covers more ground per iteration and costs proportionally more."
          >
            <input type="range" min="5" max="150" step="5" value={config.particles} onChange={(e) => update({ particles: Number(e.target.value) })} />
          </Field>
          <Field
            label={`Iterations: ${config.iterations}`}
            hint="How many rounds the swarm moves. The curve usually flattens long before the end."
          >
            <input type="range" min="50" max="2000" step="50" value={config.iterations} onChange={(e) => update({ iterations: Number(e.target.value) })} />
          </Field>
          <p className="cfg-note">
            <strong>{evaluations.toLocaleString()}</strong> route plans evaluated per algorithm.
          </p>
        </Card>

        <Card title="What counts as a good route" sub="four things, one score, lower is better">
          {[
            ["time", "Travel time", "Cost of one minute of driving. The reference unit."],
            ["distance", "Distance", "Cost of one kilometre — fuel and wear, on top of the time it takes."],
            ["congestion", "Congestion", "Extra charge per minute lost to traffic. This is what makes the optimizer avoid jams rather than merely hurry."],
            ["vehicle", "Vehicle", "Fixed cost of putting one more van on the road: driver, vehicle, depot handling."],
          ].map(([key, label, hint]) => (
            <Field key={key} label={`${label}: ${config.weights[key]}`} hint={hint}>
              <input
                type="range" min="0" max={key === "vehicle" ? 60 : 3} step={key === "vehicle" ? 1 : 0.1}
                value={config.weights[key]} onChange={(e) => updateWeight(key, Number(e.target.value))}
              />
            </Field>
          ))}
        </Card>

        <Card title="Algorithm parameters" sub="the one dial each algorithm has" className="cfg-wide">
          <Field
            label={`QPSO alpha: ${config.alpha_start} → ${config.alpha_end}`}
            hint="The contraction–expansion coefficient: one dial on how far particles jump. It shrinks across the run so the swarm explores early and refines late. Above about 1.7 the swarm never settles."
          >
            <div className="pair">
              <input type="range" min="0.2" max="1.6" step="0.05" value={config.alpha_start} onChange={(e) => update({ alpha_start: Number(e.target.value) })} />
              <input type="range" min="0.1" max="1.2" step="0.05" value={config.alpha_end} onChange={(e) => update({ alpha_end: Number(e.target.value) })} />
            </div>
          </Field>
          <Field
            label={`PSO inertia: ${config.inertia_start} → ${config.inertia_end}`}
            hint="How much momentum a particle keeps. PSO's equivalent of alpha, scheduled the same way so neither algorithm gets a better-tuned schedule."
          >
            <div className="pair">
              <input type="range" min="0.1" max="1.0" step="0.005" value={config.inertia_start} onChange={(e) => update({ inertia_start: Number(e.target.value) })} />
              <input type="range" min="0.0" max="1.0" step="0.005" value={config.inertia_end} onChange={(e) => update({ inertia_end: Number(e.target.value) })} />
            </div>
          </Field>
        </Card>

        <div className="page-actions" style={{ alignSelf: "start" }}>
          <button className="btn btn-primary" onClick={() => navigate("/run")}>Go to Run →</button>
          <button className="btn" onClick={reset}>Reset to defaults</button>
          {dirty && <span className="cfg-dirty">changed from defaults</span>}
        </div>
      </div>
    </div>
  );
}
