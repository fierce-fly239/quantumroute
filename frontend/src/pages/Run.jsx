import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { getJob, getJobResult, startSolve } from "../api.js";
import ConvergenceChart from "../components/ConvergenceChart.jsx";
import { Bar, Card, CheckItem, PageHead, Stat } from "../components/ui.jsx";
import { Activity, Gauge, Play, Send, Zap } from "../components/icons.jsx";
import { useStore } from "../store.jsx";

const POLL_MS = 120;
const NAME = { qpso: "QPSO", pso: "Classical PSO" };
const TONE = { qpso: "lilac", pso: "peach" };
const BAR = { qpso: "lilac", pso: "peach" };

export default function Run() {
  const { config, job, setJob, setResult, error, setError, log, setLog, pushAlert } = useStore();
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  // Held in a ref, not state: the polling loop needs to cancel itself on
  // unmount, and a state update would restart the effect it lives in.
  const timer = useRef(null);
  const cancelled = useRef(false);
  // /run?demo=1 starts a solve on load and jumps to the results when it lands.
  const [params] = useSearchParams();
  const autoRun = params.get("demo") === "1";
  const autoStarted = useRef(false);

  // The solver log. One line per poll that moved the iteration counter, so
  // every line is a real GET /api/jobs/{id} - nothing here is scripted.
  const lastLogged = useRef(null);
  const logBody = useRef(null);
  const LOG_MAX = 400;
  function pushLog(text, kind = "line") {
    setLog((lines) => {
      const next = lines.concat({ text, kind });
      return next.length > LOG_MAX ? next.slice(next.length - LOG_MAX) : next;
    });
  }
  useEffect(() => {
    const el = logBody.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [log]);

  useEffect(() => {
    cancelled.current = false;
    return () => {
      cancelled.current = true;
      if (timer.current) clearTimeout(timer.current);
    };
  }, []);

  async function poll(id) {
    if (cancelled.current) return;
    try {
      const status = await getJob(id);
      setJob(status);

      const stamp = `${status.phase ?? ""}:${status.iteration}`;
      if (status.iteration != null && stamp !== lastLogged.current) {
        lastLogged.current = stamp;
        const phase = (status.phase || status.status || "").toUpperCase().padEnd(4);
        const iter = String(status.iteration).padStart(String(status.total_iterations).length);
        const best = status.best_cost != null ? status.best_cost.toFixed(2) : "—";
        pushLog(`[${phase}] iter ${iter}/${status.total_iterations}   best ${best}`);
      }

      if (status.status === "done") {
        pushLog(`> done · best cost ${status.best_cost != null ? status.best_cost.toFixed(2) : "—"} · result ready`, "done");
        const result = await getJobResult(id);
        if (cancelled.current) return;
        setResult(result);
        setBusy(false);
        if (autoRun) navigate("/results", { replace: true });
        return;
      }
      if (status.status === "failed") {
        pushLog(`> failed: ${status.error || "unknown error"}`, "sys");
        setError(status.error || "The solve failed.");
        pushAlert({ kind: "error", title: "Solve failed", detail: status.error || "The API reported a failed job." });
        setBusy(false);
        return;
      }
      timer.current = setTimeout(() => poll(id), POLL_MS);
    } catch (e) {
      if (cancelled.current) return;
      setError(e.message);
      pushAlert({ kind: "error", title: "Lost the running solve", detail: e.message });
      setBusy(false);
    }
  }

  async function handleStart() {
    setError(null);
    setResult(null);
    setJob(null);
    setBusy(true);
    setLog([]);
    lastLogged.current = null;
    try {
      const { job_id } = await startSolve(config);
      const algo = config.algorithm === "both" ? "QPSO + PSO" : config.algorithm.toUpperCase();
      pushLog(`> job ${job_id} · ${algo} · ${config.network_id} · ${config.particles} particles × ${config.iterations} iterations · seed ${config.seed}${config.provider ? ` · travel times: ${config.provider}` : ""}`, "sys");
      pushLog(`> polling GET /api/jobs/${job_id} every ${POLL_MS} ms`, "sys");
      poll(job_id);
    } catch (e) {
      setError(e.message);
      pushAlert({ kind: "error", title: "Could not start the solve", detail: e.message });
      setBusy(false);
    }
  }

  // Fire the demo run once the component is mounted, never twice.
  useEffect(() => {
    if (!autoRun || autoStarted.current) return;
    autoStarted.current = true;
    handleStart();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoRun]);

  const pct = job ? Math.round(job.progress * 100) : 0;
  const finished = !busy && job?.status === "done";
  const legs = config.algorithm === "both" ? ["qpso", "pso"] : [config.algorithm];
  // Per-algorithm progress, derived from the job the API reports: a leg is
  // complete once the job's phase has moved past it or the job is done.
  function legState(name) {
    if (!job) return { pct: 0, label: "queued" };
    if (job.status === "done") return { pct: 100, label: "done" };
    if (job.phase === name) return { pct: Math.round((job.iteration / Math.max(1, job.total_iterations)) * 100), label: `iteration ${job.iteration} of ${job.total_iterations}` };
    const idx = legs.indexOf(name);
    const cur = legs.indexOf(job.phase);
    if (cur > idx) return { pct: 100, label: "done" };
    return { pct: 0, label: "queued" };
  }
  const status = !job ? "idle" : job.status === "done" ? "solve complete" : job.status === "failed" ? "failed" : "solving";

  return (
    <div className="page">
      <PageHead
        eyebrow="field ops / run"
        status={status}
        statusTone={status === "failed" ? "error" : status === "solving" ? "butter" : status === "idle" ? "lilac" : undefined}
        title="Run"
        lede="Start the optimizer and watch it work. The best score should drop quickly at first and then flatten out — that flattening is what convergence looks like."
        actions={
          <>
            {finished && <button className="btn" onClick={() => navigate("/results")}>see the routes →</button>}
            <button className="btn btn-primary" onClick={handleStart} disabled={busy}><Play /> {busy ? "solving…" : "start solve"}</button>
          </>
        }
      />

      {error && (
        <div className="notice notice-error">
          {error}
          <div className="notice-hint">
            If this says the backend is unreachable, check the API is running on port 8000. Jobs live in memory, so restarting the API clears them.
          </div>
        </div>
      )}

      <div className="stats stats-3">
        <Stat icon={<Gauge />} label="progress" value={`${pct}%`} foot={job ? `${job.iteration} / ${job.total_iterations}` : "not started"} tone="mint" delay={1} />
        <Stat icon={<Activity />} label="best cost so far" value={job?.best_cost != null ? job.best_cost.toFixed(2) : "—"} foot="lower is better" tone="peach" delay={1} />
        <Stat icon={<Zap />} label="now running" value={job?.phase ? job.phase.toUpperCase() : job?.status === "done" ? "done" : "—"} foot={`${config.particles} × ${config.iterations}`} tone="butter" delay={1} />
      </div>

      <div className="two-col-narrow">
        <Card title="Algorithm board" sub={`${config.network_id} · live from GET /api/jobs`} flush className="rise rise-2"
              action={<span className="card-sub">seed {config.seed}</span>}>
          <div className="rows">
            {legs.map((name) => {
              const st = legState(name);
              return (
                <div key={name} className="row" style={{ cursor: "default" }}>
                  <span className={`row-badge tone-${TONE[name]}`}>{name === "qpso" ? "QP" : "PS"}</span>
                  <span className="row-main">
                    <span className="row-title">{NAME[name]}</span>
                    <span className="row-sub">{name === "qpso" ? "quantum-inspired · delta potential well" : "kennedy & eberhart 1995 · inertia weight"}</span>
                  </span>
                  <span style={{ width: "40%", minWidth: 160 }}>
                    <Bar pct={st.pct} tone={BAR[name]} label={st.label} value={`${st.pct}%`} />
                  </span>
                </div>
              );
            })}
          </div>
          {!job && (
            <p style={{ padding: "8px 12px 12px", fontSize: 12, color: "var(--faint)" }}>
              Nothing has run yet. Press <b>start solve</b> — the settings come from Configure.
            </p>
          )}
        </Card>

        <Card title="Run checklist" sub="what has happened so far" className="rise rise-3" action={<Send style={{ width: 16, height: 16, color: "var(--mint-ink)" }} />}>
          <div className="checks">
            <CheckItem done={!!job}>Job accepted by the API</CheckItem>
            {legs.map((name) => (
              <CheckItem key={name} done={legState(name).pct === 100} live={job?.phase === name}>
                {NAME[name]} finished
              </CheckItem>
            ))}
            <CheckItem done={finished}>Result collected</CheckItem>
          </div>
          <div className="heads-up">
            <b>Setup:</b> {config.algorithm === "both" ? "QPSO + PSO" : config.algorithm.toUpperCase()} on {config.network_id} · {config.particles} particles × {config.iterations} iterations · {(config.particles * (config.iterations + 1)).toLocaleString()} plans per algorithm.
          </div>
        </Card>
      </div>

      {job && (
        <div className="stack mt">
          <Card title="Solver log" sub="one line per poll that moved the counter — nothing scripted" flush
                action={<span className="pill pill-lilac">{job.status === "done" ? "done" : `${job.iteration} / ${job.total_iterations}`}</span>}>
            <div className="log-body" ref={logBody} style={{ margin: -12 }}>
              {log.map((l, i) => (
                <div key={i} className={`log-line${l.kind !== "line" ? ` log-${l.kind}` : ""}`}>{l.text}</div>
              ))}
            </div>
          </Card>

          <Card title="Convergence, live" sub="best cost found so far · down is better">
            <p className="card-lede">
              When the line goes flat the swarm has contracted — the jumps are now too small to reach anywhere new.
            </p>
            <ConvergenceChart series={[{ label: "Best so far", colour: "#66529b", values: job.curve }]} />
          </Card>
        </div>
      )}
    </div>
  );
}
