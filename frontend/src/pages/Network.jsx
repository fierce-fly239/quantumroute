import { useEffect, useRef, useState } from "react";
import NetworkMap from "../components/NetworkMap.jsx";
import { Card, Note, PageHead, Stat } from "../components/ui.jsx";
import {
  ArrowUpRight, Check, Download, Layers, MapIcon, Package, Sparkles, Truck, Upload,
} from "../components/icons.jsx";
import { listNetworks, getNetwork, validateNetwork } from "../api.js";
import { useStore } from "../store.jsx";

const TONES = ["mint", "peach", "lilac", "butter", "blue"];
const CORNERS = ["mint", "lilac", "peach"];

export default function Network() {
  // The chosen scenario lives in the shared store, NOT in local state. Until
  // 7 Sep it was local, which meant switching scenario here changed the map and
  // nothing else - the Run tab kept solving whatever Configure last said.
  const { config, update, pushAlert } = useStore();
  const [scenarios, setScenarios] = useState([]);
  // true means "a network loaded from a file is being shown" - files are for
  // inspection and validation only; the solver knows built-in scenarios by id.
  const [fromFile, setFromFile] = useState(false);
  const selectedId = fromFile ? null : config.network_id;
  const [network, setNetwork] = useState(null);
  const [error, setError] = useState(null);
  const [validation, setValidation] = useState(null);
  const [loading, setLoading] = useState(true);
  const [stopId, setStopId] = useState(null);
  const [query, setQuery] = useState("");
  const fileInput = useRef(null);

  function choose(id) {
    setFromFile(false);
    update({ network_id: id });
  }

  useEffect(() => {
    listNetworks()
      .then((list) => {
        setScenarios(list);
        if (list.length && !list.some((s) => s.id === config.network_id)) {
          update({ network_id: list[0].id });
        }
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    setError(null);
    setValidation(null);
    getNetwork(selectedId)
      .then((net) => { setNetwork(net); setStopId(null); })
      .catch((e) => setError(e.message));
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
        setFromFile(true);
        setStopId(null);
      } else {
        pushAlert({
          kind: "error", title: `${file.name} failed validation`,
          detail: result.issues.map((i) => i.message).join(" · "),
        });
      }
    } catch (err) {
      const msg = err instanceof SyntaxError
        ? "That file is not valid JSON. Check for a missing comma or bracket."
        : err.message;
      setError(msg);
      pushAlert({ kind: "error", title: `${file.name} could not be read`, detail: msg });
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
  const nodes = network?.nodes ?? [];
  const depot = nodes.find((n) => n.type === "depot");
  const customers = nodes.filter((n) => n.type !== "depot");
  const visible = customers.filter((n) =>
    `${n.id} ${n.name} ${n.zone}`.toLowerCase().includes(query.toLowerCase())
  );
  const selected = nodes.find((n) => n.id === stopId) ?? depot ?? null;
  const fleetLoad = meta ? Math.round((meta.total_demand / (meta.fleet.vehicles * meta.fleet.capacity)) * 100) : 0;

  return (
    <div className="page">
      <PageHead
        eyebrow="optimization / network"
        status={network ? "ready to solve" : loading ? "loading" : "no network"}
        statusTone={network ? undefined : "butter"}
        title="Network"
        lede="The road network the optimizer works on: the depot, every delivery stop, and the roads between them with their distance, travel time and congestion."
        actions={
          <>
            <button className="btn" onClick={() => fileInput.current?.click()}><Upload /> load json</button>
            <button className="btn btn-primary" onClick={handleExport} disabled={!network}><Download /> export</button>
            <input ref={fileInput} type="file" accept="application/json,.json" onChange={handleFile} hidden />
          </>
        }
      />

      {error && (
        <div className="notice notice-error"><strong>Could not load that.</strong> {error}</div>
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
          <strong>File loaded and valid.</strong> Shown for inspection; the solver runs the built-in scenarios.
          {validation.issues.length > 0 && (
            <ul className="notice-list">
              {validation.issues.map((iss, i) => (
                <li key={i}>
                  <span className={"pill pill-" + iss.severity}>{iss.severity}</span>
                  {iss.message}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {scenarios.length > 0 && (
        <div className="scenarios rise rise-1">
          {scenarios.map((s, i) => {
            const on = s.id === selectedId;
            return (
              <button key={s.id} className={`scenario${on ? " is-active" : ""}`} onClick={() => choose(s.id)}>
                <span className={`scenario-corner corner-${CORNERS[i % CORNERS.length]}`} />
                <span className="scenario-title">
                  <span>{s.city} <span>· {s.customer_count} stops</span></span>
                  {on ? <span className="scenario-check"><Check /></span> : <span className="scenario-arrow"><ArrowUpRight /></span>}
                </span>
                <span className="scenario-meta">
                  <span className="mono">{s.fleet.vehicles} vans × {s.fleet.capacity}</span>
                  <span className="sep" />
                  <span>{s.total_demand} units of demand</span>
                </span>
              </button>
            );
          })}
        </div>
      )}

      {meta && (
        <div className="stats stats-3">
          <Stat icon={<Package />} label="delivery stops" value={meta.customer_count} foot={`${meta.node_count} places incl. depot`} tone="mint" delay={2} />
          <Stat icon={<Truck />} label="fleet" value={`${meta.fleet.vehicles} vans × ${meta.fleet.capacity}`} foot={`${fleetLoad}% loaded`} tone="peach" delay={2} />
          <Stat icon={<Layers />} label="roads modelled" value={(meta.node_count * (meta.node_count - 1)).toLocaleString()} foot="every ordered pair" tone="butter" delay={2} />
        </div>
      )}

      {network && (
        <>
          <div className="two-col">
            <Card
              className="rise rise-2 card-fill"
              icon={<MapIcon />}
              title="Network map"
              pill="live"
              sub={`${meta.city} · ${depot ? depot.name : "no depot"}`}
              flush
              action={<span className="card-sub">{nodes.length} places · click a stop to inspect it</span>}
            >
              <div style={{ margin: -12 }}>
                <NetworkMap nodes={nodes} selected={selected?.id ?? null} onSelect={setStopId} />
              </div>
            </Card>

            <Card
              className="rise rise-3"
              title="Delivery stops"
              sub={`${customers.length} deliveries · ordered as modelled`}
              flush
              action={
                <input
                  className="input" style={{ width: 150, padding: "7px 10px", fontSize: 11 }}
                  placeholder="search stops" value={query} onChange={(e) => setQuery(e.target.value)}
                  aria-label="Search stops"
                />
              }
            >
              <div className="rows rows-scroll">
                {visible.map((n, i) => (
                  <button
                    key={n.id}
                    className={`row${selected?.id === n.id ? " is-on" : ""}`}
                    onClick={() => setStopId(n.id)}
                  >
                    <span className={`row-badge tone-${TONES[i % TONES.length]}`}>{n.id.replace(/^c0?/, "")}</span>
                    <span className="row-main">
                      <span className="row-title">{n.name}</span>
                      <span className="row-sub">{n.zone} · {n.demand} units</span>
                    </span>
                    <span className="row-end">{n.lat.toFixed(3)}, {n.lng.toFixed(3)}</span>
                  </button>
                ))}
                {visible.length === 0 && (
                  <p style={{ padding: "32px 12px", textAlign: "center", fontSize: 12, color: "var(--faint)" }}>
                    No stops match “{query}”.
                  </p>
                )}
              </div>
              <div className="card-foot">
                <div className="bar-row"><span>fleet capacity used</span><span className="mono">{fleetLoad}%</span></div>
                <div className="bar bar-mint"><span style={{ width: `${Math.min(100, fleetLoad)}%` }} /></div>
              </div>
            </Card>
          </div>

          <div className="two-col-narrow mt">
            <Card
              title="Selected place"
              sub={`inspection / ${selected?.id ?? "—"}`}
              action={<span className={`pill ${selected?.type === "depot" ? "pill-lilac" : "pill-peach"}`}>{selected?.type === "depot" ? "depot" : "delivery"}</span>}
            >
              {selected && (
                <>
                  <h3 className="stop-title">{selected.name}</h3>
                  <p className="stop-sub">{selected.zone} · {meta.city}</p>
                  <div className="detail-grid">
                    <div className="detail"><div className="detail-l">demand</div><div className="detail-v">{selected.type === "depot" ? "—" : `${selected.demand} units`}</div></div>
                    <div className="detail"><div className="detail-l">zone</div><div className="detail-v">{selected.zone}</div></div>
                    <div className="detail"><div className="detail-l">position</div><div className="detail-v mono" style={{ fontSize: 12 }}>{selected.lat.toFixed(4)}, {selected.lng.toFixed(4)}</div></div>
                  </div>
                </>
              )}
            </Card>
            <Note eyebrow="about this scenario" icon={<Sparkles />} title={meta.name}>
              <p>{meta.description}</p>
            </Note>
          </div>
        </>
      )}

      {!network && !error && loading && <div className="notice">Loading networks…</div>}
    </div>
  );
}
