import { createFileRoute } from "@tanstack/react-router";
import { startGmailOAuth } from "@/lib/gmail-oauth.server";

export const Route = createFileRoute("/api/gmail/connect")({
  server: { handlers: { GET: ({ request }) => startGmailOAuth(request) } },
});
