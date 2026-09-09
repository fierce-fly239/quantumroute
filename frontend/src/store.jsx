/** One place for the state the four pages share.
 *
 *  Configure writes the settings, Run starts a job and watches it, Results reads
 *  what came back. Without somewhere shared, choosing a scenario on one page and
 *  running it on another would mean threading props through the router, or
 *  re-fetching and re-solving on every navigation.
 *
 *  Deliberately a plain context and useState rather than a state library: there
 *  are four pages and one object. Anything heavier would be more machinery than
 *  the app has state.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

// Defaults are the TUNED values from the Phase 3 sweep, not the ones published
// in Sun's paper. See quantumroute_kb/Wiki/benchmark-results.md - the published
// alpha of 1.0 -> 0.5 is miscalibrated for permutation encodings and costs
// about 12% on the 49-stop network.
export const DEFAULT_CONFIG = {
  network_id: "ggn-10",
  algorithm: "both",
  particles: 40,
  iterations: 500,
  seed: 42,
  weights: { time: 1.0, distance: 0.5, congestion: 0.3, vehicle: 15.0 },
  alpha_start: 0.9,
  alpha_end: 0.4,
  inertia_start: 0.729,
  inertia_end: 0.729,
};

const StoreContext = createContext(null);

// Config and the last finished result survive a page reload. This is not a
// nicety: on demo day someone will refresh, or the laptop will sleep, and
// losing a finished solve at that moment means re-running it in front of the
// judges. sessionStorage rather than localStorage so a genuinely fresh session
// starts clean.
//
// Every access is wrapped: private windows and blocked site data make these
// throw rather than return null, and a storage failure must never stop the app
// from rendering.
const KEY = "quantumroute-v1";

function load() {
  try {
    const raw = sessionStorage.getItem(KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function save(config, result) {
  try {
    sessionStorage.setItem(KEY, JSON.stringify({ config, result }));
  } catch {
    /* storage blocked or full - the app works, it just will not remember */
  }
}

export function StoreProvider({ children }) {
  const saved = load();
  const [config, setConfig] = useState(saved?.config ?? DEFAULT_CONFIG);
  const [job, setJob] = useState(null);      // live status while running
  // The solver log lives here rather than in the Run page so it survives a
  // trip to Results and back. Not persisted: it belongs to the job, and jobs
  // die with the API process.
  const [log, setLog] = useState([]);
  const [result, setResult] = useState(saved?.result ?? null); // finished solve
  const [error, setError] = useState(null);

  useEffect(() => {
    save(config, result);
  }, [config, result]);

  const update = useCallback((patch) => {
    setConfig((c) => ({ ...c, ...patch }));
  }, []);

  const updateWeight = useCallback((key, value) => {
    setConfig((c) => ({ ...c, weights: { ...c.weights, [key]: value } }));
  }, []);

  const reset = useCallback(() => setConfig(DEFAULT_CONFIG), []);

  const value = useMemo(
    () => ({
      config, setConfig, update, updateWeight, reset,
      job, setJob, result, setResult, error, setError, log, setLog,
    }),
    [config, update, updateWeight, reset, job, result, error, log]
  );

  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}

export function useStore() {
  const ctx = useContext(StoreContext);
  if (!ctx) throw new Error("useStore must be used inside <StoreProvider>");
  return ctx;
}
