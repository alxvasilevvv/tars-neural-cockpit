import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    host: "127.0.0.1",
    port: 5174,
  },
  build: {
    target: "es2022",
    sourcemap: false,
    rollupOptions: {
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
