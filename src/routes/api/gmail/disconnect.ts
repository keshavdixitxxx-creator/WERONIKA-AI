import { createFileRoute } from "@tanstack/react-router";
import { disconnectGmail } from "@/lib/gmail-oauth.server";

export const Route = createFileRoute("/api/gmail/disconnect")({
  server: { handlers: { POST: ({ request }) => disconnectGmail(request) } },
});
