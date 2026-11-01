import { createFileRoute } from "@tanstack/react-router";
import { prepareGmailSend } from "@/lib/gmail-oauth.server";

export const Route = createFileRoute("/api/gmail/prepare-send")({
  server: { handlers: { POST: ({ request }) => prepareGmailSend(request) } },
});
