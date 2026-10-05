/// <reference types="vitest/config" />
/**
 * Vite: the dev server and the build tool for Atrium.
 *
 * LEARN, two security choices here:
 *  1. PROXY: the browser calls /v1/... on the SAME origin (localhost:5173) and Vite
 *     forwards it to the Conductor. No cross-origin requests in development.
 *  2. CSP: production builds get a strict Content-Security-Policy: scripts, styles,
 *     fonts and API calls only from this app's own origin. (frame-ancestors
 *     only works as a real HTTP header, so set it on the web server in production.) (Not in dev: Vite's
 *     hot-reload needs inline scripts.)
 */
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv, type Plugin } from "vite";

const CSP = [
  "default-src 'self'",
  "script-src 'self'",
  "style-src 'self' 'unsafe-inline'",
  "font-src 'self'",
  "img-src 'self' data:",
  "connect-src 'self'",
  "base-uri 'self'",
  "form-action 'self'",
].join("; ");

function contentSecurityPolicy(): Plugin {
  return {
    name: "atrium-csp",
    apply: "build",
    transformIndexHtml: (html) =>
      html.replace("<head>", `<head>\n    <meta http-equiv="Content-Security-Policy" content="${CSP}">`),
  };
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  const conductor = env["CONDUCTOR_URL"] ?? "http://127.0.0.1:8000";
  const proxy = { "/v1": { target: conductor, changeOrigin: true } };
  return {
    plugins: [react(), contentSecurityPolicy()],
    server: { host: "127.0.0.1", port: 5173, strictPort: true, proxy },
    preview: { host: "127.0.0.1", port: 4173, strictPort: true, proxy },
    build: { sourcemap: false },
    test: { environment: "jsdom", setupFiles: ["./tests/setup.ts"], css: false },
  };
});
