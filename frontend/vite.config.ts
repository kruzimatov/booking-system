import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    // Same origin in development, so the httpOnly auth cookie works exactly as in production.
    proxy: { "/api": "http://localhost:8000" },
  },
});
