import { Routes, Route, Navigate } from "react-router-dom";
import Sidebar, { MobileNav } from "./components/Sidebar.jsx";
import Topbar from "./components/Topbar.jsx";
import { StoreProvider } from "./store.jsx";
import Network from "./pages/Network.jsx";
import Configure from "./pages/Configure.jsx";
import Run from "./pages/Run.jsx";
import Results from "./pages/Results.jsx";
import Alerts from "./pages/Alerts.jsx";
import Settings from "./pages/Settings.jsx";
import Team from "./pages/Team.jsx";

export default function App() {
  return (
    <StoreProvider>
      <div className="app">
        <Sidebar />
        <div className="main">
          <Topbar />
          <MobileNav />
          <Routes>
            <Route path="/" element={<Navigate to="/network" replace />} />
            <Route path="/network" element={<Network />} />
            <Route path="/configure" element={<Configure />} />
            <Route path="/run" element={<Run />} />
            <Route path="/results" element={<Results />} />
            <Route path="/alerts" element={<Alerts />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/team" element={<Team />} />
            <Route path="*" element={<Navigate to="/network" replace />} />
          </Routes>
        </div>
      </div>
    </StoreProvider>
  );
}
