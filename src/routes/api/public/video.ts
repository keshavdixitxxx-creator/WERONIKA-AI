import { createFileRoute } from "@tanstack/react-router";

import { rejectCloudMediaGeneration, rejectCloudMediaStatus } from "@/lib/local-media-only.server";

export const Route = createFileRoute("/api/public/video")({
  server: {
    handlers: {
      GET: () => rejectCloudMediaStatus(),
      POST: ({ request }) => rejectCloudMediaGeneration("video", request),
    },
  },
});
