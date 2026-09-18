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
import { useTheme } from "../theme.js";

const ESRI_ATTR =
  'Tiles &copy; <a href="https://www.esri.com/">Esri</a> &mdash; sources: Esri, HERE, Garmin, ' +
  'OpenStreetMap contributors, and the GIS user community';

export const BASEMAPS = {
  lightGrayLabelled: {
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
    labels:
      "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}",
    attribution: ESRI_ATTR,
  },
  darkGrayLabelled: {
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
    labels:
      "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}",
    attribution: ESRI_ATTR,
  },
};

/** The basemap that matches the current theme. Esri ships the same canvas in a
 *  dark variant, so the map no longer sits as a bright rectangle inside the
 *  dark UI. Returned with a `key` so a TileLayer can be re-created when the
 *  theme flips - react-leaflet does not swap a layer's URL in place.
 *  CartoDB was evaluated and rejected: its tiles now return an
 *  "API KEY REQUIRED" watermark. */
export function useBasemap() {
  const theme = useTheme();
  const map = theme === "dark" ? BASEMAPS.darkGrayLabelled : BASEMAPS.lightGrayLabelled;
  return { ...map, key: theme };
}

/** Palette from the Pastel Route Console design (18 Sep 2026): charcoal depot,
 *  purple-ringed cream stops, coral for the selected one. The depot flips to
 *  peach on the dark basemap, where charcoal would vanish. */
export const DEPOT_COLOR = "#29233f";
export const DEPOT_COLOR_DARK = "#f4b48e";
export const CUSTOMER_COLOR = "#66529b";
export const CUSTOMER_FILL = "#fffaf2";
export const SELECTED_COLOR = "#e78368";

export function useDepotColour() {
  return useTheme() === "dark" ? DEPOT_COLOR_DARK : DEPOT_COLOR;
}

/** One colour per van, in the design's family but saturated enough to read on
 *  a grey basemap and to stay distinct when a deck is printed in greyscale.
 *  Neither depot colour is in this list, on purpose: van 2 was once drawn in
 *  exactly the depot's colour and the depot disappeared into a route. */
export const VAN_COLOURS = [
  "#66529b", "#3a9a78", "#e78368", "#c99a2e", "#4e7fa3",
  "#b9557c", "#7a9a3a", "#d97a3a", "#2f8f9a", "#8067b7",
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

/** Flies to one point when it changes, keeping the current zoom. Used when a
 *  stop is picked from the list beside the map. */
export function PanTo({ point }) {
  const map = useMap();
  useEffect(() => {
    if (point) map.panTo(point, { animate: true, duration: 0.4 });
  }, [point, map]);
  return null;
}
