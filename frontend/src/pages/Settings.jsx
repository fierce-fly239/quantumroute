import { useEffect, useState } from "react";
import { getTraffic, refreshTraffic } from "../api.js";
import { Card, Note, PageHead, Stat, Toast } from "../components/ui.jsx";
import { Activity, Check, Moon, Refresh, Sparkles, Sun, Zap } from "../components/icons.jsx";
import { setTheme, useTheme } from "../theme.js";
import { useStore } from "../store.jsx";

const STALE_HOURS = 12;
// TomTom bills max(origins, destinations) x 5 per matrix when both exceed 5.
const COST = { "ggn-10": 50, "ggn-50": 250, "blr-10": 50 };

function hoursOld(iso) {
  return iso ? (Date.now() - new Date(iso).getTime()) / 36e5 : null;
}
function fmt(iso) {
  return iso ? new Date(iso).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "never";
}

export default function Settings() {
  const theme = useTheme();
  const { config, update, pushAlert } = useStore();
  const [traffic, setTraffic] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(null);      // network id being refreshed
  const [toast, setToast] = useState("");

  function say(text) {
    setToast(text);
    window.setTimeout(() => setToast(""), 2800);
  }

  async function load() {
    try {
      const t = await getTraffic();
      setTraffic(t);
      setError(null);
      // Stale snapshots are worth an alert, once per page visit.
      for (const [id, snap] of Object.entries(t.snapshots)) {
        const h = hoursOld(snap?.fetched_at);
        if (h != null && h > STALE_HOURS) {
          pushAlert({ key: `stale-${id}`, kind: "warn", title: `TomTom snapshot for ${id} is ${Math.round(h)} h old`, detail: "Solves on the tomtom provider use this snapshot. Refresh it on Settings if you want current traffic." });
        }
      }
    } catch (e) {
      setError(e.message);
    }
  }
  useEffect(() => { load(); /* eslint-disable-line react-hooks/exhaustive-deps */ }, []);

  async function refresh(id) {
    const cost = COST[id] ?? "some";
    if (!window.confirm(`Fetch live traffic for ${id} from TomTom now?\n\nThis spends about ${cost} of the 2,500 free monthly transactions.`)) return;
    setBusy(id);
    setError(null);
    try {
      const src = await refreshTraffic(id);
      say(`${id}: live travel times frozen at ${fmt(src.fetched_at)} · ${src.transactions} transactions`);
      pushAlert({ kind: "ok", title: `TomTom snapshot refreshed for ${id}`, detail: `${src.cells} cells in ${src.fetch_seconds}s via the ${src.endpoint} endpoint · ${src.transactions} transactions.` });
      await load();
    } catch (e) {
      setError(e.message);
      pushAlert({ kind: "error", title: `TomTom refresh failed for ${id}`, detail: e.message });
    } finally {
      setBusy(null);
    }
  }

  const provider = config.provider ?? "default";
  const effective = config.provider ?? traffic?.default_provider ?? "simulated";
  const snaps = traffic ? Object.entries(traffic.snapshots) : [];
  const withSnap = snaps.filter(([, s]) => s).length;
  const newest = snaps.map(([, s]) => s?.fetched_at).filter(Boolean).sort().pop();

  return (
    <div className="page">
      <PageHead
        eyebrow="workspace / settings"
        status={effective === "tomtom" ? "tomtom live traffic" : "simulated traffic"}
        statusTone={effective === "tomtom" ? undefined : "lilac"}
        title="Settings"
        lede="Where the travel times come from, and how the console looks. Both are saved in this browser."
      />

      {error && <div className="notice notice-error">{error}</div>}

      <div className="stats stats-3">
        <Stat icon={<Zap />} label="travel times" value={effective} foot={config.provider ? "chosen here" : "server default"} tone="mint" delay={1} />
        <Stat icon={<Activity />} label="tomtom key" value={traffic ? (traffic.tomtom_key_present ? "present" : "missing") : "…"} foot="backend/.env" tone={traffic?.tomtom_key_present ? "mint" : "peach"} delay={1} />
        <Stat icon={<Refresh />} label="snapshots" value={traffic ? `${withSnap} / ${snaps.length}` : "…"} foot={newest ? `newest ${fmt(newest)}` : "none yet"} tone="lilac" delay={1} />
      </div>

      <div className="two-col-narrow">
        <Card title="Travel-time source" sub="what the solver prices roads with" className="rise rise-2">
          <div className="checks" style={{ gap: 10 }}>
            {[
              ["default", "Server default", "Whatever QR_TRAVEL_PROVIDER says on the backend — simulated unless someone changed it."],
              ["simulated", "Simulated", "The zone-based congestion model in geo.py. Deterministic, identical on every run: this is the benchmark instance."],
              ["tomtom", "TomTom live traffic", "Real road distances and live travel times, frozen to a snapshot per network. Every solve reads the snapshot until you refresh it."],
            ].map(([value, label, hint]) => (
              <label key={value} className={`row${provider === value ? " is-on" : ""}`} style={{ alignItems: "flex-start", cursor: "pointer" }}>
                <input type="radio" name="provider" value={value} checked={provider === value}
                       onChange={() => update({ provider: value === "default" ? null : value })}
                       style={{ marginTop: 4, accentColor: "var(--purple)" }} />
                <span className="row-main">
                  <span className="row-title">{label}</span>
                  <span className="row-sub" style={{ fontFamily: "var(--font-sans)", fontSize: 12, color: "var(--muted)", whiteSpace: "normal" }}>{hint}</span>
                </span>
              </label>
            ))}
          </div>

          <div className="cfg-note" style={{ marginTop: 20 }}>
            <strong>Snapshots</strong> — refresh is a button, not something the app does by itself. One refresh of the 50-stop network costs 250 of the 2,500 free monthly transactions.
          </div>
          <div className="rows" style={{ marginTop: 8 }}>
            {snaps.map(([id, s]) => {
              const h = hoursOld(s?.fetched_at);
              return (
                <div key={id} className="row" style={{ cursor: "default" }}>
                  <span className={`row-badge ${s ? (h > STALE_HOURS ? "tone-butter" : "tone-mint") : "tone-lilac"}`}>{s ? <Check /> : "—"}</span>
                  <span className="row-main">
                    <span className="row-title">{id}</span>
                    <span className="row-sub">
                      {s ? `frozen ${fmt(s.fetched_at)} · roads priced for ${s.departure_time ? new Date(s.departure_time).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" }) : "—"} · ${s.cells} cells · ${s.endpoint}` : "no snapshot yet — the first tomtom solve fetches one"}
                    </span>
                  </span>
                  <button className="btn btn-sm" onClick={() => refresh(id)} disabled={busy != null || !traffic?.tomtom_key_present}>
                    <Refresh /> {busy === id ? "fetching…" : `refresh · ${COST[id] ?? "?"}`}
                  </button>
                </div>
              );
            })}
          </div>
        </Card>

        <div className="stack">
          <Note eyebrow="display" icon={<Sparkles />} title={theme === "dark" ? "Pastel dark mode" : "Pastel light mode"}
                actions={
                  <>
                    <button className={`btn btn-sm${theme === "light" ? " btn-primary" : ""}`} onClick={() => setTheme("light")}><Sun /> light</button>
                    <button className={`btn btn-sm${theme === "dark" ? " btn-primary" : ""}`} onClick={() => setTheme("dark")}><Moon /> dark</button>
                  </>
                }>
            <p>Light is the safer choice on a projector. The map tiles follow the theme.</p>
          </Note>
          <Note eyebrow="why a snapshot" icon={<Zap />} title="Frozen on purpose." tone="mint">
            <p>
              QPSO and PSO must be scored against the same numbers or the comparison means nothing.
              Live traffic changes minute to minute, so a fetch is frozen and every solve after it reads the frozen copy.
            </p>
          </Note>
        </div>
      </div>
      <Toast text={toast} />
    </div>
  );
}
