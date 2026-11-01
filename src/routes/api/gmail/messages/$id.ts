import { createFileRoute } from "@tanstack/react-router";
import { getGmailMessage } from "@/lib/gmail-oauth.server";

export const Route = createFileRoute("/api/gmail/messages/$id")({
  server: { handlers: { GET: ({ request, params }) => getGmailMessage(request, params.id) } },
});
