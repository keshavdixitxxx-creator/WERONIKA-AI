// @lovable.dev/vite-tanstack-config already includes the following — do NOT add them manually
// or the app will break with duplicate plugins:
//   - TanStack devtools (dev-only, first), tanstackStart, viteReact, tailwindcss, tsConfigPaths,
//     nitro (build-only using cloudflare as a default target), VITE_* env injection, @ path alias,
//     React/TanStack dedupe, error logger plugins, and sandbox detection (port/host/strictPort).
// You can pass additional config via defineConfig({ vite: { ... }, etc... }) if needed.
import { defineConfig } from "@lovable.dev/vite-tanstack-config";
import type {} from "nitro/vite";

export default defineConfig({
  tanstackStart: {
    // Redirect TanStack Start's bundled server entry to src/server.ts (our SSR error wrapper).
    // nitro/vite builds from this
    server: { entry: "server" },
  },
  vite: {
    nitro: {
      // This root-level file is from a different app layout; TanStack Start uses src/server.ts.
      serverEntry: false,
    },
    server: {
      host: "0.0.0.0",
      allowedHosts: true,
      proxy: {
        "/api/weronika-agent": {
          target: "http://127.0.0.1:8765",
          changeOrigin: true,
          rewrite: (path: string) => path.replace(/^\/api\/weronika-agent/, "") || "/",
        },
      },
    },
  },
});
