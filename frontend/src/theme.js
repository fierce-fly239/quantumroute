/** Theme = light | dark. Three states, like the OS: an explicit choice is
 *  stamped on <html data-theme>; no choice means follow prefers-color-scheme.
 *
 *  The maps need to know the theme too (dark tiles under a dark UI), and they
 *  live outside React's theme context, so this is a tiny store with a
 *  subscribe function rather than a context. */
import { useEffect, useState } from "react";

const KEY = "quantumroute-theme";
const media = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;
const listeners = new Set();

export function currentTheme() {
  const stamped = document.documentElement.dataset.theme;
  if (stamped === "dark" || stamped === "light") return stamped;
  return media && media.matches ? "dark" : "light";
}

export function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  try { localStorage.setItem(KEY, theme); } catch { /* private window: theme just does not persist */ }
  listeners.forEach((fn) => fn(theme));
}

export function toggleTheme() {
  setTheme(currentTheme() === "dark" ? "light" : "dark");
}

if (media) {
  const onChange = () => listeners.forEach((fn) => fn(currentTheme()));
  if (media.addEventListener) media.addEventListener("change", onChange);
  else media.addListener(onChange);
}

export function useTheme() {
  const [theme, set] = useState(currentTheme);
  useEffect(() => {
    listeners.add(set);
    return () => listeners.delete(set);
  }, []);
  return theme;
}
