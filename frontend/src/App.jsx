import { Routes, Route, Navigate } from "react-router-dom";
import Nav from "./components/Nav.jsx";
import { StoreProvider } from "./store.jsx";
import Network from "./pages/Network.jsx";
import Configure from "./pages/Configure.jsx";
import Run from "./pages/Run.jsx";
import Results from "./pages/Results.jsx";

export default function App() {
  return (
    <StoreProvider>
      <div className="app">
        <Nav />
        <main className="main">
          <Routes>
            <Route path="/" element={<Navigate to="/network" replace />} />
            <Route path="/network" element={<Network />} />
            <Route path="/configure" element={<Configure />} />
            <Route path="/run" element={<Run />} />
            <Route path="/results" element={<Results />} />
            <Route path="*" element={<Navigate to="/network" replace />} />
          </Routes>
        </main>
      </div>
    </StoreProvider>
  );
}
