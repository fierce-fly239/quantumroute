import { useEffect } from "react";
import { Card, Note, PageHead, Stat } from "../components/ui.jsx";
import { Activity, AlertIcon, Bell, Check, Sparkles } from "../components/icons.jsx";
import { useStore } from "../store.jsx";

/** Things that actually happened. Nothing here is seeded: an empty list means
 *  nothing has gone wrong this session, which is the normal state. */

const TONE = { error: "peach", warn: "butter", ok: "mint", info: "lilac" };
const ICON = { error: <AlertIcon />, warn: <Bell />, ok: <Check />, info: <Activity /> };

function ago(ts) {
  const s = Math.max(0, Math.round((Date.now() - ts) / 1000));
  if (s < 60) return `${s}s ago`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  return h < 24 ? `${h} hr ago` : new Date(ts).toLocaleString();
}

export default function Alerts() {
  const { alerts, unreadAlerts, markAlertsRead, clearAlerts } = useStore();

  // Opening the page reads them.
  useEffect(() => {
    if (unreadAlerts) markAlertsRead();
  }, [unreadAlerts, markAlertsRead]);

  const errors = alerts.filter((a) => a.kind === "error").length;
  const latest = alerts[0];

  return (
    <div className="page">
      <PageHead
        eyebrow="workspace / alerts"
        status={errors ? `${errors} problem${errors > 1 ? "s" : ""}` : "all clear"}
        statusTone={errors ? "error" : undefined}
        title="Alerts"
        lede="Only what actually happened this session: the API going away, a file that failed validation, a solve that failed, a traffic snapshot going stale."
        actions={<button className="btn" onClick={clearAlerts} disabled={!alerts.length}><Check /> clear all</button>}
      />

      <div className="stats stats-3">
        <Stat icon={<Bell />} label="events this session" value={alerts.length} foot={latest ? ago(latest.at) : "nothing yet"} tone="mint" delay={1} />
        <Stat icon={<AlertIcon />} label="problems" value={errors} foot={errors ? "need attention" : "none"} tone={errors ? "peach" : "mint"} delay={1} />
        <Stat icon={<Activity />} label="api" value={alerts.find((a) => a.key === "api-down" || a.key === "api-back")?.key === "api-down" ? "down" : "reachable"} foot="GET /api/health every 10 s" tone="lilac" delay={1} />
      </div>

      <div className="two-col-narrow">
        <Card title="Recent alerts" sub="newest first" flush className="rise rise-2"
              action={unreadAlerts ? <span className="pill pill-peach">{unreadAlerts} unread</span> : <span className="pill">up to date</span>}>
          {alerts.length === 0 ? (
            <p style={{ padding: "40px 12px", textAlign: "center", fontSize: 13, color: "var(--faint)" }}>
              Nothing to report. That is the good outcome.
            </p>
          ) : (
            <div className="rows">
              {alerts.map((a) => (
                <div key={a.id} className="row" style={{ cursor: "default", alignItems: "flex-start" }}>
                  <span className={`row-badge tone-${TONE[a.kind] ?? "lilac"}`}>{ICON[a.kind] ?? ICON.info}</span>
                  <span className="row-main">
                    <span className="row-title" style={{ whiteSpace: "normal" }}>{a.title}</span>
                    <span className="row-sub" style={{ fontFamily: "var(--font-sans)", fontSize: 12, color: "var(--muted)", whiteSpace: "normal" }}>{a.detail}</span>
                  </span>
                  <span className="row-end">{ago(a.at)}</span>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Note eyebrow="what raises an alert" icon={<Sparkles />} title="Real events only.">
          <p>
            The API health check failing, a JSON network that does not validate, a solve the API reports as failed,
            and a TomTom snapshot older than twelve hours. There is no notification the app invents to look busy.
          </p>
        </Note>
      </div>
    </div>
  );
}
