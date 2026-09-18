import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// `npm run dev` proxies the API to `oeisbot dashboard`; `npm run build` writes into the Python package.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://127.0.0.1:8765" } },
  build: { outDir: "../oeisbot/dashboard/static", emptyOutDir: true },
});
