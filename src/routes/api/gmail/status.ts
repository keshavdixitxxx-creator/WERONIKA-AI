import { createFileRoute } from "@tanstack/react-router";
import { gmailStatus } from "@/lib/gmail-oauth.server";

export const Route = createFileRoute("/api/gmail/status")({
  server: { handlers: { GET: ({ request }) => gmailStatus(request) } },
});
