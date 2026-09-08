import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  resolve: {
    // react-leaflet must use the same React instance as the app. Without this,
    // a stale pre-bundle can hand it a second copy and every hook call fails.
    dedupe: ["react", "react-dom"],
  },
  optimizeDeps: {
    include: ["react", "react-dom", "react-router-dom", "react-leaflet", "leaflet"],
  },
  server: {
    port: 5173,
    // Anything the app requests at /api goes to the FastAPI server.
    // This keeps the browser talking to a single origin in development.
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
