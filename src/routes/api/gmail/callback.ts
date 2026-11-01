import { createFileRoute } from "@tanstack/react-router";
import { completeGmailOAuth } from "@/lib/gmail-oauth.server";

export const Route = createFileRoute("/api/gmail/callback")({
  server: { handlers: { GET: ({ request }) => completeGmailOAuth(request) } },
});
