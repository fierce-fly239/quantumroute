import { MapContainer, TileLayer, CircleMarker, Popup, Tooltip } from "react-leaflet";
import { useMemo } from "react";
import "leaflet/dist/leaflet.css";
import {
  AutoResize, CUSTOMER_COLOR, CUSTOMER_FILL, FitToPoints, PanTo, SELECTED_COLOR,
  useBasemap, useDepotColour,
} from "./mapBase.jsx";

/** The network on a real map. `selected` / `onSelect` link it to the stop list
 *  beside it: pick a stop in the list and the map pans to it; click a marker
 *  and the list follows. */
export default function NetworkMap({ nodes, selected = null, onSelect }) {
  const depot = nodes.find((n) => n.type === "depot");
  const center = depot ? [depot.lat, depot.lng] : [28.47, 77.03];
  // Memoised so FitToPoints does not refit on every unrelated re-render.
  const points = useMemo(() => nodes.map((n) => [n.lat, n.lng]), [nodes]);
  const BASEMAP = useBasemap();
  const depotColour = useDepotColour();
  const sel = nodes.find((n) => n.id === selected);
  const selPoint = useMemo(() => (sel ? [sel.lat, sel.lng] : null), [sel]);

  return (
    <div className="map-wrap">
      <MapContainer
        center={center}
        zoom={12}
        scrollWheelZoom
        className="map"
        // Zoom animation is ON: without it every zoom is a hard jump, which
        // reads as broken next to any map people already use. AutoResize above
        // is what makes it safe, by never re-measuring mid-animation.
        //
        // Tile fade stays OFF. It was the other half of the stuck-state bug,
        // and nobody has ever noticed a tile fading in. No upside, real
        // downside.
        fadeAnimation={false}
      >
        <TileLayer
          key={`base-${BASEMAP.key}`}
          attribution={BASEMAP.attribution}
          url={BASEMAP.url}
          keepBuffer={4}
          updateWhenZooming={false}
        />
        {BASEMAP.labels && (
          <TileLayer key={`labels-${BASEMAP.key}`} url={BASEMAP.labels} keepBuffer={4} updateWhenZooming={false} />
        )}
        <AutoResize />
        <FitToPoints points={points} />
        <PanTo point={selPoint} />

        {nodes.map((n) => {
          const isDepot = n.type === "depot";
          const isSel = n.id === selected;
          return (
            <CircleMarker
              key={n.id}
              center={[n.lat, n.lng]}
              radius={isDepot ? 10 : isSel ? 9 : 7}
              pathOptions={{
                color: isDepot ? "#ffffff" : isSel ? "#29233f" : CUSTOMER_COLOR,
                weight: isDepot ? 3 : 2.2,
                fillColor: isDepot ? depotColour : isSel ? SELECTED_COLOR : CUSTOMER_FILL,
                fillOpacity: 1,
              }}
              eventHandlers={onSelect ? { click: () => onSelect(n.id) } : undefined}
            >
              {!isDepot && (
                <Tooltip direction="right" offset={[6, 0]} opacity={0.95}>
                  {n.id.toUpperCase()}
                </Tooltip>
              )}
              <Popup>
                <div className="popup">
                  <strong>{n.name}</strong>
                  <div className="popup-row">
                    {isDepot ? "Depot — every route starts and ends here" : `Demand: ${n.demand} units`}
                  </div>
                  <div className="popup-row popup-dim">Zone: {n.zone}</div>
                  <div className="popup-row popup-dim">
                    {n.lat.toFixed(4)}, {n.lng.toFixed(4)} · id {n.id}
                  </div>
                </div>
              </Popup>
            </CircleMarker>
          );
        })}
      </MapContainer>

      <div className="map-legend">
        <div className="map-legend-title">map legend</div>
        <div className="map-legend-grid">
          <span className="legend-item"><span className="dot" style={{ background: depotColour }} /> depot</span>
          <span className="legend-item"><span className="dot" style={{ background: CUSTOMER_FILL, borderColor: CUSTOMER_COLOR }} /> delivery stop</span>
          <span className="legend-item"><span className="dot" style={{ background: SELECTED_COLOR }} /> selected</span>
          <span className="legend-item"><span className="mono">{nodes.length}</span> places</span>
        </div>
      </div>
    </div>
  );
}
