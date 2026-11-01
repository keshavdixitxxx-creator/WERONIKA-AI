import { createFileRoute } from "@tanstack/react-router";
import { listGmailMessages } from "@/lib/gmail-oauth.server";

export const Route = createFileRoute("/api/gmail/messages/")({
  server: { handlers: { GET: ({ request }) => listGmailMessages(request) } },
});
