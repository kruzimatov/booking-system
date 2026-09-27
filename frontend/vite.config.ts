import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  const apiTarget = env.VITE_API_PROXY_TARGET || "http://localhost:8000";
  const isRemoteTarget = !apiTarget.includes("localhost") && !apiTarget.includes("127.0.0.1");
  const targetOrigin = new URL(apiTarget).origin;

  return {
    plugins: [react()],
    server: {
      proxy: {
        "/api": {
          target: apiTarget,
          changeOrigin: true,
          secure: true,
          // The remote API's production cookie is HTTPS-only and may have a
          // production domain. Rewrite it only in local remote-proxy mode.
          ...(isRemoteTarget
            ? {
                cookieDomainRewrite: "",
                cookiePathRewrite: "/api",
                headers: { origin: targetOrigin },
              }
            : {}),
        },
      },
    },
  };
});
