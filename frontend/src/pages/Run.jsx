import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { getJob, getJobResult, startSolve } from "../api.js";
import ConvergenceChart from "../components/ConvergenceChart.jsx";
import { useStore } from "../store.jsx";

const POLL_MS = 120;

export default function Run() {
  const { config, job, setJob, setResult, error, setError } = useStore();
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  // Held in a ref, not state: the polling loop needs to cancel itself on
  // unmount, and a state update would restart the effect it lives in.
  const timer = useRef(null);
  const cancelled = useRef(false);
  // /run?demo=1 starts a solve on load and jumps to the results when it lands.
  // One URL that takes the whole app from cold to a finished answer - useful
  // when demoing, and the only way to capture the finished page in a single
  // page load (state lives in sessionStorage, which is per-tab).
  const [params] = useSearchParams();
  const autoRun = params.get("demo") === "1";
  const autoStarted = useRef(false);

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

      if (status.status === "done") {
        const result = await getJobResult(id);
        if (cancelled.current) return;
        setResult(result);
        setBusy(false);
        if (autoRun) navigate("/results", { replace: true });
        return;
      }
      if (status.status === "failed") {
        setError(status.error || "The solve failed.");
        setBusy(false);
        return;
      }
      timer.current = setTimeout(() => poll(id), POLL_MS);
    } catch (e) {
      if (cancelled.current) return;
      setError(e.message);
      setBusy(false);
    }
  }

  async function handleStart() {
    setError(null);
    setResult(null);
    setJob(null);
    setBusy(true);
    try {
      const { job_id } = await startSolve(config);
      poll(job_id);
    } catch (e) {
      setError(e.message);
      setBusy(false);
    }
  }

  // Fire the demo run once the component is mounted, never twice.
  useEffect(() => {
    if (!autoRun || autoStarted.current) return;
    autoStarted.current = true;
    handleStart();
    // handleStart is stable enough for this one-shot; re-running on every render
    // would start a new solve each time.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoRun]);

  const running = busy && job && job.status !== "done";
  const pct = job ? Math.round(job.progress * 100) : 0;
  const finished = !busy && job?.status === "done";

  return (
    <div className="page">
      <div className="page-head">
        <h1>Run</h1>
        <p className="page-lede">
          Start the optimizer and watch it work. The best score should drop
          quickly at first and then flatten out — that flattening is what
          convergence looks like.
        </p>
      </div>

      <div className="toolbar">
        <button className="btn btn-primary" onClick={handleStart} disabled={busy}>
          {busy ? "Solving…" : "Start solve"}
        </button>
        {finished && (
          <button className="btn" onClick={() => navigate("/results")}>
            See the routes →
          </button>
        )}
        <span className="run-config">
          {config.algorithm === "both" ? "QPSO + PSO" : config.algorithm.toUpperCase()} ·{" "}
          {config.network_id} · {config.particles}×{config.iterations} · seed {config.seed}
        </span>
      </div>

      {error && (
        <div className="notice notice-error">
          {error}
          <div className="notice-hint">
            If this says the backend is unreachable, check the API is running on
            port 8000. Jobs live in memory, so restarting the API clears them.
          </div>
        </div>
      )}

      {job && (
        <>
          <div className="stats">
            <div className="stat">
              <div className="stat-n">{pct}%</div>
              <div className="stat-l">Progress</div>
            </div>
            <div className="stat">
              <div className="stat-n">{job.iteration}</div>
              <div className="stat-l">Iteration of {job.total_iterations}</div>
            </div>
            <div className="stat">
              <div className="stat-n">
                {job.best_cost != null ? job.best_cost.toFixed(2) : "—"}
              </div>
              <div className="stat-l">Best cost so far</div>
            </div>
            <div className="stat">
              <div className="stat-n">
                {job.phase ? job.phase.toUpperCase() : job.status === "done" ? "Done" : "—"}
              </div>
              <div className="stat-l">Now running</div>
            </div>
          </div>

          <div className="progress-track" aria-hidden="true">
            <span className="progress-fill" style={{ width: `${pct}%` }} />
          </div>

          <section className="panel">
            <h2>Convergence, live</h2>
            <p className="panel-lede">
              Best cost found so far. Down is better. When the line goes flat the
              swarm has contracted — the jumps are now too small to reach
              anywhere new.
            </p>
            <ConvergenceChart
              series={[{ label: "Best so far", colour: "#0e6c7d", values: job.curve }]}
            />
          </section>
        </>
      )}

      {!job && !error && (
        <div className="notice">
          Nothing has run yet. Press <strong>Start solve</strong> — the settings
          come from the Configure tab.
        </div>
      )}
    </div>
  );
}
