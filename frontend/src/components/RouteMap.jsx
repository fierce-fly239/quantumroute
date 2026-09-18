/** The solved network: one coloured line per van, the depot in the design's
 *  charcoal (peach on the dark basemap).
 *
 *  Lines are drawn stop to stop. They are the VISITING ORDER, not the road
 *  geometry a driver would follow - we model roads as weighted edges between
 *  places, not as polylines, so drawing anything else would be inventing detail
 *  the model does not have. The popup on each stop says where it sits in the
 *  sequence, which is the information the line is actually carrying.
 */
import { useMemo } from "react";
import { CircleMarker, MapContainer, Polyline, Popup, TileLayer } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { AutoResize, FitToPoints, useBasemap, useDepotColour, vanColour } from "./mapBase.jsx";

export default function RouteMap({ routes, depot, highlight = null }) {
  const points = useMemo(
    () => routes.flatMap((r) => r.path),
    [routes]
  );
  const center = depot?.at ?? [28.47, 77.03];
  const BASEMAP = useBasemap();
  const depotColour = useDepotColour();

  return (
    <div className="map-wrap">
      <MapContainer center={center} zoom={12} scrollWheelZoom className="map map-tall" fadeAnimation={false}>
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

        {routes.map((r, i) => {
          const dimmed = highlight !== null && highlight !== r.van;
          return (
            <Polyline
              key={`line-${r.van}`}
              positions={r.path}
              pathOptions={{
                color: vanColour(i),
                weight: dimmed ? 2 : 3.5,
                opacity: dimmed ? 0.22 : 0.9,
                dashArray: "6 4",
              }}
            />
          );
        })}

        {routes.map((r, i) =>
          r.stops.map((s, k) => {
            const dimmed = highlight !== null && highlight !== r.van;
            return (
              <CircleMarker
                key={`stop-${r.van}-${k}`}
                center={s.at}
                radius={6}
                pathOptions={{
                  color: "#fffaf2",
                  weight: 2,
                  fillColor: vanColour(i),
                  fillOpacity: dimmed ? 0.25 : 1,
                }}
              >
                <Popup>
                  <div className="popup">
                    <strong>{s.name}</strong>
                    <div className="popup-row">
                      Van {r.van}, stop {k + 1} of {r.stops.length}
                    </div>
                    <div className="popup-row popup-dim">{s.demand} units</div>
                  </div>
                </Popup>
              </CircleMarker>
            );
          })
        )}

        {depot && (
          <CircleMarker
            center={depot.at}
            radius={10}
            pathOptions={{ color: "#ffffff", weight: 3, fillColor: depotColour, fillOpacity: 1 }}
          >
            <Popup>
              <div className="popup">
                <strong>{depot.name}</strong>
                <div className="popup-row">Depot — every van starts and ends here</div>
              </div>
            </Popup>
          </CircleMarker>
        )}
      </MapContainer>
    </div>
  );
}
