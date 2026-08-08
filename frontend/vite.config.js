import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");

  return {
    plugins: [react()],
    server: {
      host: "0.0.0.0",
      port: 4173,
      strictPort: true,
      proxy: {
        "/api": {
          target: env.API_PROXY_URL || "http://localhost:8080",
          changeOrigin: true,
        },
      },
    },
  };
});
