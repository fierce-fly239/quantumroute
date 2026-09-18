/** One place for the state the pages share.
 *
 *  Configure writes the settings, Run starts a job and watches it, Results reads
 *  what came back. Without somewhere shared, choosing a scenario on one page and
 *  running it on another would mean threading props through the router, or
 *  re-fetching and re-solving on every navigation.
 *
 *  Deliberately a plain context and useState rather than a state library: there
 *  are a few pages and one object. Anything heavier would be more machinery than
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
  // Where travel times come from: null = whatever the server's default is
  // (simulated unless QR_TRAVEL_PROVIDER says otherwise). Set on Settings.
  provider: null,
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

function save(config, result, alerts) {
  try {
    sessionStorage.setItem(KEY, JSON.stringify({ config, result, alerts }));
  } catch {
    /* storage blocked or full - the app works, it just will not remember */
  }
}

const ALERTS_MAX = 50;

export function StoreProvider({ children }) {
  const saved = load();
  const [config, setConfig] = useState({ ...DEFAULT_CONFIG, ...(saved?.config ?? {}) });
  const [job, setJob] = useState(null);      // live status while running
  // The solver log lives here rather than in the Run page so it survives a
  // trip to Results and back. Not persisted: it belongs to the job, and jobs
  // die with the API process.
  const [log, setLog] = useState([]);
  const [result, setResult] = useState(saved?.result ?? null); // finished solve
  const [error, setError] = useState(null);
  // Alerts are things that actually happened: the API going away, a file that
  // failed validation, a solve that failed, a traffic snapshot going stale.
  // Nothing is seeded; an empty list is the normal state.
  const [alerts, setAlerts] = useState(saved?.alerts ?? []);

  useEffect(() => {
    save(config, result, alerts);
  }, [config, result, alerts]);

  const update = useCallback((patch) => {
    setConfig((c) => ({ ...c, ...patch }));
  }, []);

  const updateWeight = useCallback((key, value) => {
    setConfig((c) => ({ ...c, weights: { ...c.weights, [key]: value } }));
  }, []);

  const reset = useCallback(() => setConfig((c) => ({ ...DEFAULT_CONFIG, provider: c.provider })), []);

  // `key` de-duplicates: the same condition reported twice in a row (the API
  // polled every 10 s while down) is one alert, not sixty.
  const pushAlert = useCallback((a) => {
    setAlerts((list) => {
      if (a.key && list.length && list[0].key === a.key) return list;
      const entry = { id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`, at: Date.now(), read: false, ...a };
      return [entry, ...list].slice(0, ALERTS_MAX);
    });
  }, []);
  const markAlertsRead = useCallback(() => setAlerts((list) => list.map((a) => ({ ...a, read: true }))), []);
  const clearAlerts = useCallback(() => setAlerts([]), []);
  const unreadAlerts = alerts.filter((a) => !a.read).length;

  const value = useMemo(
    () => ({
      config, setConfig, update, updateWeight, reset,
      job, setJob, result, setResult, error, setError, log, setLog,
      alerts, pushAlert, markAlertsRead, clearAlerts, unreadAlerts,
    }),
    [config, update, updateWeight, reset, job, result, error, log, alerts, pushAlert, markAlertsRead, clearAlerts, unreadAlerts]
  );

  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}

export function useStore() {
  const ctx = useContext(StoreContext);
  if (!ctx) throw new Error("useStore must be used inside <StoreProvider>");
  return ctx;
}
