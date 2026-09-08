import { MapContainer, TileLayer, CircleMarker, Popup } from "react-leaflet";
import { useMemo } from "react";
import "leaflet/dist/leaflet.css";
import {
  AutoResize, BASEMAP, CUSTOMER_COLOR, DEPOT_COLOR, FitToPoints,
} from "./mapBase.jsx";

export default function NetworkMap({ nodes }) {
  const depot = nodes.find((n) => n.type === "depot");
  const center = depot ? [depot.lat, depot.lng] : [28.47, 77.03];
  // Memoised so FitToPoints does not refit on every unrelated re-render.
  const points = useMemo(() => nodes.map((n) => [n.lat, n.lng]), [nodes]);

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
        {/* Basemap. Switch by changing BASEMAP below. All options are keyless.
            CartoDB was evaluated and rejected: its tiles now return an
            "API KEY REQUIRED" watermark. */}
        <TileLayer
          attribution={BASEMAP.attribution}
          url={BASEMAP.url}
          keepBuffer={4}
          updateWhenZooming={false}
        />
        {BASEMAP.labels && (
          <TileLayer url={BASEMAP.labels} keepBuffer={4} updateWhenZooming={false} />
        )}
        <AutoResize />
        <FitToPoints points={points} />

        {nodes.map((n) => {
          const isDepot = n.type === "depot";
          return (
            <CircleMarker
              key={n.id}
              center={[n.lat, n.lng]}
              radius={isDepot ? 10 : 7}
              pathOptions={{
                color: "#ffffff",
                weight: 2,
                fillColor: isDepot ? DEPOT_COLOR : CUSTOMER_COLOR,
                fillOpacity: 0.95,
              }}
            >
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

      <div className="legend">
        <span className="legend-item">
          <span className="dot" style={{ background: DEPOT_COLOR }} /> Depot
        </span>
        <span className="legend-item">
          <span className="dot" style={{ background: CUSTOMER_COLOR }} /> Delivery stop
        </span>
      </div>
    </div>
  );
}
