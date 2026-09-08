import { useEffect, useState } from "react";

/**
 * Calls the API's health endpoint and shows whether the backend is reachable.
 * In the skeleton this is the proof that both halves of the stack are wired
 * together: if this reads "API connected", the frontend really is talking to
 * FastAPI through the Vite proxy.
 */
export default function BackendStatus() {
  const [state, setState] = useState("checking");

  useEffect(() => {
    let cancelled = false;

    async function check() {
      try {
        const res = await fetch("/api/health");
        if (!res.ok) throw new Error(String(res.status));
        await res.json();
        if (!cancelled) setState("up");
      } catch {
        if (!cancelled) setState("down");
      }
    }

    check();
    const timer = setInterval(check, 10000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  const label = {
    checking: "Checking API",
    up: "API connected",
    down: "API not running",
  }[state];

  return (
    <div className={"status status-" + state} title={
      state === "down" ? "Start the backend, or use ./run.sh to start both" : undefined
    }>
      <span className="status-dot" aria-hidden="true" />
      {label}
    </div>
  );
}
