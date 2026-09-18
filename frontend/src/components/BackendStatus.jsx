import { useEffect, useRef, useState } from "react";
import { Activity } from "./icons.jsx";
import { useStore } from "../store.jsx";

/**
 * Calls the API's health endpoint and shows whether the backend is reachable.
 * This is the real thing behind the design's "Systems nominal" pill: it goes
 * green only when GET /api/health answers, and red the moment it stops. A
 * change to red also raises an alert, once, so the Alerts page has the time.
 */
export default function BackendStatus() {
  const [state, setState] = useState("checking");
  const { pushAlert } = useStore();
  const last = useRef("checking");

  useEffect(() => {
    let cancelled = false;

    async function check() {
      let next;
      try {
        const res = await fetch("/api/health");
        if (!res.ok) throw new Error(String(res.status));
        await res.json();
        next = "up";
      } catch {
        next = "down";
      }
      if (cancelled) return;
      setState(next);
      if (next === "down" && last.current !== "down") {
        pushAlert({
          key: "api-down", kind: "error", title: "API not reachable",
          detail: "GET /api/health failed. Start the backend on port 8000, or run ./run.sh to start both halves.",
        });
      }
      if (next === "up" && last.current === "down") {
        pushAlert({ key: "api-back", kind: "ok", title: "API back", detail: "GET /api/health is answering again." });
      }
      last.current = next;
    }

    check();
    const timer = setInterval(check, 10000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [pushAlert]);

  const label = { checking: "Checking API", up: "API connected", down: "API not running" }[state];

  return (
    <div className={"status status-" + state} title={
      state === "down" ? "Start the backend, or use ./run.sh to start both" : "GET /api/health, every 10 s"
    }>
      <span className="status-dot" aria-hidden="true" />
      <span>{label}</span>
      <Activity style={{ width: 14, height: 14 }} />
    </div>
  );
}
