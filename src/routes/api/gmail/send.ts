import { createFileRoute } from "@tanstack/react-router";
import { sendPreparedGmailReply } from "@/lib/gmail-oauth.server";

export const Route = createFileRoute("/api/gmail/send")({
  server: { handlers: { POST: ({ request }) => sendPreparedGmailReply(request) } },
});
