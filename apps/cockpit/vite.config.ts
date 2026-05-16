import { defineConfig } from "vite";

// TARS cockpit (W308) — output is consumed by the desktop release
// pipeline once step 2 ships. Until then `pnpm dev` is the only
// caller, so the config stays intentionally minimal.
export default defineConfig({
  base: "./",
  build: {
    target: "es2022",
    outDir: "dist",
    emptyOutDir: true,
    sourcemap: true,
    cssMinify: true,
    rollupOptions: {
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
