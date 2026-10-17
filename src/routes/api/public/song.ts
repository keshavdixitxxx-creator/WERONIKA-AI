import { createFileRoute } from "@tanstack/react-router";

import { rejectCloudMediaGeneration } from "@/lib/local-media-only.server";

export const Route = createFileRoute("/api/public/song")({
  server: {
    handlers: {
      POST: ({ request }) => rejectCloudMediaGeneration("song", request),
    },
  },
});
