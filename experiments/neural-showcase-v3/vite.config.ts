/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

export default defineConfig({
  // GitHub Pages project sites live under /<repo>/ ; set VITE_BASE_PATH in CI
  // (see .github/workflows/cockpit-github-pages.yml). Local dev uses `/`.
  base: process.env.VITE_BASE_PATH ?? "/",
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
      // Legal / security pages render the canonical markdown from docs/
      // via `?raw` imports — single source of truth.
      "@docs": path.resolve(__dirname, "../../docs"),
    },
    // Force a single resolved copy of `three` across the app, R3F,
    // postprocessing, drei, and our shader-lines port. Without this,
    // Vite's dev pre-bundler can ship two separate `three` chunks and
    // the runtime fires `THREE.WARNING: Multiple instances of Three.js`.
    dedupe: ["three", "react", "react-dom"],
  },
  optimizeDeps: {
    include: ["three"],
  },
  server: {
    host: "127.0.0.1",
    port: 5174,
    fs: {
      // Allow imports from the parent docs/ folder for legal pages
      allow: [path.resolve(__dirname, "../..")],
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
  },
  build: {
    target: "es2022",
    sourcemap: false,
    // The Spline runtime (physics, navmesh, react-spline) is the
    // largest dep and intentionally lazy-loaded inside <MeetTars />.
    // Raising the chunk-size warning so the build log only screams
    // when something genuinely regresses, not when Spline is doing
    // its expected weight.
    chunkSizeWarningLimit: 2200,
    rollupOptions: {
      // Tauri runtime modules (`@tauri-apps/api/*`,
      // `@tauri-apps/plugin-*`) are deliberately NOT installed as
      // cockpit dependencies — the cockpit ships as a static web app
      // *and* gets bundled into the desktop shell where Tauri injects
      // these modules into the page at runtime. Mark them external so
      // Rollup doesn't try to resolve them at build time (the dynamic
      // `import()` calls in `useTarsDeepLink.ts`, `useSidecarStatus.ts`,
      // and `Settings.tsx` are guarded by `__TAURI_INTERNALS__` checks
      // and a try/catch — they're effectively dead code in the web
      // build and only execute inside the Tauri shell).
      external: [
        /^@tauri-apps\/api(\/.*)?$/,
        /^@tauri-apps\/plugin-.*/,
      ],
      output: {
        manualChunks(id) {
          if (id.includes("node_modules/three")) return "three-vendor";
          if (
            id.includes("node_modules/@react-three") ||
            id.includes("/node_modules/react-three-")
          )
            return "r3f-vendor";
          if (id.includes("/node_modules/react-dom/") || id.includes("/node_modules/react/"))
            return "react-vendor";
          return undefined;
        },
      },
    },
  },
});
