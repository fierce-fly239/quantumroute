import { useLocation } from "react-router-dom";
import BackendStatus from "./BackendStatus.jsx";
import { Moon, Sun } from "./icons.jsx";
import { toggleTheme, useTheme } from "../theme.js";
import { Brand } from "./Sidebar.jsx";

const NAMES = {
  "/network": "Network", "/configure": "Configure", "/run": "Run", "/results": "Results",
  "/alerts": "Alerts", "/settings": "Settings", "/team": "Team",
};

function ThemeToggle() {
  const dark = useTheme() === "dark";
  return (
    <button
      type="button" className="icon-btn" onClick={toggleTheme}
      title={dark ? "Switch to light mode" : "Switch to dark mode"}
      aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
    >
      {dark ? <Sun /> : <Moon />}
    </button>
  );
}

export default function Topbar() {
  const { pathname } = useLocation();
  const name = NAMES[pathname] ?? "Network";
  return (
    <header className="topbar">
      <div className="crumbs">
        <span className="topbar-brand-mobile"><Brand /></span>
        <span className="crumb-text">Operations</span>
        <span className="sep">/</span>
        <b>{name}</b>
      </div>
      <div className="top-right">
        <BackendStatus />
        <ThemeToggle />
      </div>
    </header>
  );
}
