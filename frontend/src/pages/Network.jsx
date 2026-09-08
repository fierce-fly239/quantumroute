import { useEffect, useState, useRef } from "react";
import NetworkMap from "../components/NetworkMap.jsx";
import { listNetworks, getNetwork, validateNetwork } from "../api.js";
import { useStore } from "../store.jsx";

export default function Network() {
  // The chosen scenario lives in the shared store, NOT in local state. Until
  // 7 Sep it was local, which meant switching scenario here changed the map and
  // nothing else - the Run tab kept solving whatever Configure last said. The
  // demo runbook's "switch to 50 stops on Network, then Run" would have quietly
  // solved the 10-stop network again.
  const { config, update } = useStore();
  const [scenarios, setScenarios] = useState([]);
  // null means "a network loaded from a file is being shown" - files are for
  // inspection and validation only; the solver knows built-in scenarios by id.
  const [fromFile, setFromFile] = useState(false);
  const selectedId = fromFile ? null : config.network_id;
  const setSelectedId = (id) => {
    if (id) {
      setFromFile(false);
      update({ network_id: id });
    } else {
      setFromFile(true);
    }
  };
  const [network, setNetwork] = useState(null);
  const [error, setError] = useState(null);
  const [validation, setValidation] = useState(null);
  const [loading, setLoading] = useState(true);
  const fileInput = useRef(null);

  // Load the list of built-in scenarios once.
  useEffect(() => {
    listNetworks()
      .then((list) => {
        setScenarios(list);
        // Only fall back to the first scenario if the store holds nothing usable.
        if (list.length && !list.some((s) => s.id === config.network_id)) {
          update({ network_id: list[0].id });
        }
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  // Load whichever scenario is selected.
  useEffect(() => {
    if (!selectedId) return;
    setError(null);
    setValidation(null);
    getNetwork(selectedId)
      .then(setNetwork)
      .catch((e) => setError(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId]);

  async function handleFile(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setValidation(null);
    try {
      const parsed = JSON.parse(await file.text());
      const result = await validateNetwork(parsed);
      setValidation(result);
      if (result.valid) {
        setNetwork(parsed);
        setSelectedId(null);
      }
    } catch (err) {
      setError(
        err instanceof SyntaxError
          ? "That file is not valid JSON. Check for a missing comma or bracket."
          : err.message
      );
    } finally {
      e.target.value = "";
    }
  }

  function handleExport() {
    if (!network) return;
    const blob = new Blob([JSON.stringify(network, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${network.meta.id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const meta = network?.meta;

  return (
    <div className="page page-wide">
      <div className="page-head">
        <h1>Network</h1>
        <p className="page-lede">
          The road network the optimizer works on: the depot, every delivery stop,
          and the roads between them with their distance, travel time and congestion.
        </p>
      </div>

      <div className="toolbar">
        <div className="field">
          <label htmlFor="scenario">Scenario</label>
          <select
            id="scenario"
            value={selectedId ?? ""}
            onChange={(e) => setSelectedId(e.target.value)}
            disabled={loading || !scenarios.length}
          >
            {!selectedId && <option value="">Loaded from file</option>}
            {scenarios.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </div>

        <div className="toolbar-actions">
          <button className="btn" onClick={() => fileInput.current?.click()}>
            Load JSON
          </button>
          <button className="btn" onClick={handleExport} disabled={!network}>
            Export JSON
          </button>
          <input
            ref={fileInput}
            type="file"
            accept="application/json,.json"
            onChange={handleFile}
            hidden
          />
        </div>
      </div>

      {error && (
        <div className="notice notice-error">
          <strong>Could not load that.</strong> {error}
        </div>
      )}

      {validation && !validation.valid && (
        <div className="notice notice-error">
          <strong>That network cannot be solved as it stands.</strong>
          <ul className="notice-list">
            {validation.issues.map((iss, i) => (
              <li key={i}>
                <span className={"pill pill-" + iss.severity}>{iss.severity}</span>
                {iss.message}
                {iss.hint && <div className="notice-hint">{iss.hint}</div>}
              </li>
            ))}
          </ul>
        </div>
      )}

      {validation?.valid && (
        <div className="notice notice-ok">
          <strong>File loaded and valid.</strong>
          {validation.issues.length > 0 && (
            <ul className="notice-list">
              {validation.issues.map((iss, i) => (
                <li key={i}>
                  <span className={"pill pill-" + iss.severity}>{iss.severity}</span>
                  {iss.message}
                  {iss.hint && <div className="notice-hint">{iss.hint}</div>}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {meta && (
        <>
          <div className="stats">
            <div className="stat">
              <div className="stat-n">{meta.customer_count}</div>
              <div className="stat-l">Delivery stops</div>
            </div>
            <div className="stat">
              <div className="stat-n">{meta.fleet.vehicles}</div>
              <div className="stat-l">Vans available</div>
            </div>
            <div className="stat">
              <div className="stat-n">{meta.fleet.capacity}</div>
              <div className="stat-l">Units per van</div>
            </div>
            <div className="stat">
              <div className="stat-n">{meta.total_demand}</div>
              <div className="stat-l">Total demand</div>
            </div>
            <div className="stat">
              <div className="stat-n">
                {Math.round((meta.total_demand / (meta.fleet.vehicles * meta.fleet.capacity)) * 100)}%
              </div>
              <div className="stat-l">Fleet loaded</div>
            </div>
            <div className="stat">
              <div className="stat-n">{meta.node_count * (meta.node_count - 1)}</div>
              <div className="stat-l">Roads modelled</div>
            </div>
          </div>
          <p className="scenario-note">{meta.description}</p>
        </>
      )}

      {network && <NetworkMap nodes={network.nodes} />}

      {!network && !error && loading && <div className="notice">Loading networks…</div>}
    </div>
  );
}
