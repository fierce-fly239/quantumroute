/** Shared map machinery.
 *
 *  Extracted from NetworkMap when the Results page needed a second map. Both
 *  maps must behave identically - same basemap, same resize handling, same
 *  colours - and the surest way to guarantee that is for there to be one copy.
 *
 *  The AutoResize logic in particular is hard-won: see the comment on it.
 */
import { useEffect } from "react";
import { useMap } from "react-leaflet";

const ESRI_ATTR =
  'Tiles &copy; <a href="https://www.esri.com/">Esri</a> &mdash; sources: Esri, HERE, Garmin, ' +
  'OpenStreetMap contributors, and the GIS user community';

export const BASEMAPS = {
  osm: {
    url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  },
  lightGray: {
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
    attribution: ESRI_ATTR,
  },
  lightGrayLabelled: {
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
    labels:
      "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}",
    attribution: ESRI_ATTR,
  },
  street: {
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
    attribution: ESRI_ATTR,
  },
};

// The basemap in use. Each provider requires its own attribution, which is why
// attribution travels with the URL rather than being hardcoded in the JSX.
// CartoDB was evaluated and rejected: its tiles now return an
// "API KEY REQUIRED" watermark.
export const BASEMAP = BASEMAPS.lightGrayLabelled;

export const DEPOT_COLOR = "#d1442f";
export const CUSTOMER_COLOR = "#2f7fd1";

/** One colour per van. Distinguishable on a light grey basemap, and still
 *  distinguishable when a deck is printed in greyscale.
 *
 *  DEPOT_COLOR's red is deliberately absent from this list. It was in it, which
 *  meant van 2 was drawn in exactly the depot's colour - on the map the depot
 *  became indistinguishable from one of the routes. */
export const VAN_COLOURS = [
  "#2f7fd1", "#2e8b57", "#8a4fbd", "#c9820b", "#0e8f8f",
  "#b3376f", "#5a6b1f", "#3f5fa8", "#7a5c2e", "#4a4a8a",
];

export const vanColour = (i) => VAN_COLOURS[i % VAN_COLOURS.length];

/** Keeps Leaflet's idea of the container size honest, without fighting animations.
 *
 *  Two things are true at once:
 *
 *  1. Leaflet measures its container once and caches it. If the container then
 *     changes size - window resized, sidebar opened, projector at a different
 *     resolution - the cached size is stale, tiles position themselves
 *     off-screen and fitBounds picks the wrong zoom. invalidateSize() fixes it.
 *
 *  2. But invalidateSize() *during* a zoom animation is what caused the bugs
 *     seen on 5 Sep: Leaflet applies a scale transform to the tile layer and an
 *     opacity to each tile while animating, and re-measuring mid-flight freezes
 *     them there. Tiles ended up stuck at opacity 0.
 *
 *  So: re-measure, but never while a zoom is in flight. If a resize lands
 *  mid-zoom, remember it and apply it once the zoom finishes.
 */
export function AutoResize() {
  const map = useMap();

  // Dev-only handle so the map can be inspected and driven from the console
  // while building. Stripped from production builds by the DEV guard.
  useEffect(() => {
    if (import.meta.env.DEV) window.__map = map;
  }, [map]);

  useEffect(() => {
    let frame = 0;
    let zooming = false;
    let deferred = false;

    const remeasure = () => {
      if (zooming) {
        deferred = true;
        return;
      }
      map.invalidateSize();
    };

    const onZoomStart = () => {
      zooming = true;
    };
    const onZoomEnd = () => {
      zooming = false;
      if (deferred) {
        deferred = false;
        map.invalidateSize();
      }
    };

    const observer = new ResizeObserver(() => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(remeasure);
    });
    observer.observe(map.getContainer());
    map.on("zoomstart", onZoomStart);
    map.on("zoomend", onZoomEnd);

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      map.off("zoomstart", onZoomStart);
      map.off("zoomend", onZoomEnd);
    };
  }, [map]);
  return null;
}

/** Pans and zooms so every point in `points` is visible whenever they change.
 *  Lives as a child component because fitBounds needs the map instance, and
 *  useMap only works inside MapContainer. */
export function FitToPoints({ points }) {
  const map = useMap();
  useEffect(() => {
    if (!points || !points.length) return;
    // Re-measure before fitting: fitBounds against a stale size picks the
    // wrong zoom, which is how a city-sized network ends up as a tiny clump.
    map.invalidateSize();
    map.fitBounds(points, { padding: [45, 45], maxZoom: 14, animate: false });
  }, [points, map]);
  return null;
}
