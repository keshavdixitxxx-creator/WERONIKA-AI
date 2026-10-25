// @lovable.dev/vite-tanstack-config already includes the app's TanStack, React,
// Tailwind, Nitro, alias, and sandbox plugins. Keep the dev server preview-host friendly.
import { defineConfig } from "@lovable.dev/vite-tanstack-config";
import type {} from "nitro/vite";

export default defineConfig({
  tanstackStart: {
    server: { entry: "server" },
  },
  vite: {
    nitro: {
      serverEntry: false,
    },
    server: {
      host: "0.0.0.0",
      allowedHosts: true,
    },
  },
});
