import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The dashboard talks to the FastAPI backend on :8000. In dev we proxy
// /api (including the WebSocket /api/live) so the frontend can use same-origin
// relative URLs in every environment.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        ws: true,
      },
      "/health": { target: "http://localhost:8000", changeOrigin: true },
      "/ready": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
  preview: {
    port: 4173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        ws: true,
      },
      "/health": { target: "http://localhost:8000", changeOrigin: true },
      "/ready": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
