import { defineConfig } from "vite";
import { resolve } from "node:path";

// TARS cockpit (W308) — multi-page Vite project.
//
// Pages:
//   /              → index.html       — landing / page picker
//   /cockpit.html  → cockpit.html     — operator shell (ported from W307 ref)
//   /hero.html     → hero.html        — marketing hero (ported from W307 ref)
//   /preview.html  → preview.html     — design-system diagnostic surface
//
// Dev server picks up every .html in the project root automatically;
// build only emits the entries enumerated below.
export default defineConfig({
  base: "./",
  build: {
    target: "es2022",
    outDir: "dist",
    emptyOutDir: true,
    sourcemap: true,
    cssMinify: true,
    rollupOptions: {
      input: {
        main: resolve(__dirname, "index.html"),
        cockpit: resolve(__dirname, "cockpit.html"),
        hero: resolve(__dirname, "hero.html"),
        preview: resolve(__dirname, "preview.html"),
      },
      output: {
        // Predictable filenames keep cockpit smoke tests stable.
        entryFileNames: "assets/cockpit-[hash].js",
        chunkFileNames: "assets/cockpit-[hash].js",
        assetFileNames: "assets/cockpit-[hash][extname]",
      },
    },
  },
  server: {
    host: "127.0.0.1",
    strictPort: true,
  },
  preview: {
    host: "127.0.0.1",
    strictPort: true,
  },
});
