import { NavLink } from "react-router-dom";
import BackendStatus from "./BackendStatus.jsx";
import { toggleTheme, useTheme } from "../theme.js";

// The four pages map onto the components SIH26137 names as required:
// network modelling, parameter/constraint setup, convergence monitoring,
// and results with benchmarking. The labels stay short on purpose - the demo
// runbook refers to them by these names.
const PAGES = [
  { to: "/network", label: "Network", hint: "1" },
  { to: "/configure", label: "Configure", hint: "2" },
  { to: "/run", label: "Run", hint: "3" },
  { to: "/results", label: "Results", hint: "4" },
];

function ThemeToggle() {
  const theme = useTheme();
  const dark = theme === "dark";
  return (
    <button
      type="button"
      className="theme-btn"
      onClick={toggleTheme}
      title={dark ? "Switch to light mode" : "Switch to dark mode"}
      aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
    >
      <span aria-hidden="true">{dark ? "☀️" : "🌙"}</span>
      <span>{dark ? "Light mode" : "Dark mode"}</span>
    </button>
  );
}

export default function Nav() {
  return (
    <header className="nav">
      <div className="nav-inner">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true" />
          <div className="brand-name">
            QuantumRoute <span className="brand-sub">SIH26137</span>
          </div>
        </div>

        <nav className="tabs" aria-label="Main">
          {PAGES.map((p) => (
            <NavLink
              key={p.to}
              to={p.to}
              className={({ isActive }) => "tab" + (isActive ? " is-active" : "")}
            >
              <span className="tab-num">{p.hint}</span>
              {p.label}
            </NavLink>
          ))}
        </nav>

        <div className="nav-right">
          <ThemeToggle />
          <BackendStatus />
        </div>
      </div>
    </header>
  );
}
