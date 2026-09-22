import { NavLink } from "react-router-dom";
import { useStore } from "../store.jsx";
import { Bell, Chart, Grid, RouteIcon, Send, Settings } from "./icons.jsx";

// The four workspace pages map onto the components SIH26137 names as required:
// network modelling, parameter setup, convergence monitoring, results with
// benchmarking. The labels are ours, not the design's ("Routes / Dispatch /
// Insights"): the pitch script and the runbook use these names, and "Dispatch"
// would tell a judge we send drivers out, which we do not.
export const WORKSPACE = [
  { to: "/network", label: "Network", icon: Grid },
  { to: "/configure", label: "Configure", icon: RouteIcon },
  { to: "/run", label: "Run", icon: Send },
  { to: "/results", label: "Results", icon: Chart },
];

function Item({ to, label, icon: Icon, badge }) {
  return (
    <NavLink to={to} className={({ isActive }) => "side-item" + (isActive ? " is-active" : "")}>
      {({ isActive }) => (
        <>
          <Icon />
          {label}
          {badge > 0 ? <span className="side-badge">{badge}</span> : isActive && <span className="side-dot" />}
        </>
      )}
    </NavLink>
  );
}

export function Brand() {
  return (
    <div className="brand">
      <span className="brand-mark" aria-hidden="true">Q</span>
      <div>
        <div className="brand-name">QuantumRoute</div>
        <div className="brand-sub">SIH26137 / CYBER POOKIES _26</div>
      </div>
    </div>
  );
}

export default function Sidebar() {
  const { unreadAlerts } = useStore();
  return (
    <aside className="sidebar">
      <Brand />
      <div className="side-label">workspace</div>
      <nav className="side-nav" aria-label="Primary">
        {WORKSPACE.map((p) => <Item key={p.to} {...p} />)}
      </nav>
      <div className="side-bottom">
        <Item to="/alerts" label="Alerts" icon={Bell} badge={unreadAlerts} />
        <Item to="/settings" label="Settings" icon={Settings} />
        <NavLink to="/team" className="side-team">
          <span className="side-avatar">CP</span>
          <span>
            <span className="side-team-name">Cyber Pookies _26</span><br />
            <span className="side-team-sub">team · vedam</span>
          </span>
        </NavLink>
      </div>
    </aside>
  );
}

/** Narrow screens: the sidebar folds into a scrolling strip under the top bar. */
export function MobileNav() {
  const { unreadAlerts } = useStore();
  return (
    <nav className="mobile-nav" aria-label="Primary">
      {WORKSPACE.map((p) => <Item key={p.to} {...p} />)}
      <Item to="/alerts" label="Alerts" icon={Bell} badge={unreadAlerts} />
      <Item to="/settings" label="Settings" icon={Settings} />
    </nav>
  );
}
