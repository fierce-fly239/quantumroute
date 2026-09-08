import { NavLink } from "react-router-dom";
import BackendStatus from "./BackendStatus.jsx";

// The four pages map onto the components SIH26137 names as required:
// network modelling, parameter/constraint setup, convergence monitoring,
// and results with benchmarking.
const PAGES = [
  { to: "/network", label: "Network", hint: "1" },
  { to: "/configure", label: "Configure", hint: "2" },
  { to: "/run", label: "Run", hint: "3" },
  { to: "/results", label: "Results", hint: "4" },
];

export default function Nav() {
  return (
    <header className="nav">
      <div className="nav-inner">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true" />
          <div>
            <div className="brand-name">QuantumRoute</div>
            <div className="brand-sub">SIH26137</div>
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

        <BackendStatus />
      </div>
    </header>
  );
}
