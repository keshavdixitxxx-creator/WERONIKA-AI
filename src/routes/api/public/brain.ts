import { createFileRoute } from "@tanstack/react-router";
import { generateText } from "ai";

import { createLovableAiGatewayProvider } from "@/lib/ai-gateway.server";
import { HOSTED_ORIGINS } from "@/lib/relay.server";
import {
  BRAIN_MODEL,
  RESPONSES_URL,
  buildAutomationPlanInstructions,
  buildInstructions,
  buildMediaIntentInstructions,
  buildResponsesBody,
  isTransientStatus,
  readResponseDeltas,
  sanitizeAddressName,
  sanitizeGatewayMessage,
  sanitizeHistory,
  sanitizeLang,
  sseEvent,
  type HistoryItem,
} from "@/lib/brain-stream.server";

const MAX_TRANSIENT_RETRIES = 2;
const CHAT_COMPLETIONS_URL = "https://ai.gateway.lovable.dev/v1/chat/completions";
const CHAT_MODELS = ["google/gemini-3.8-flash", "google/gemini-3.7-flash", BRAIN_MODEL] as const;
type BrainInput = {
  message: string;
  history: HistoryItem[];
  lang: string;
  addressName: string;
  task?: "media-intent" | "automation-plan";
};

function instructionsFor(input: Pick<BrainInput, "lang" | "addressName" | "task">) {
  if (input.task === "media-intent") return buildMediaIntentInstructions();
  if (input.task === "automation-plan") return buildAutomationPlanInstructions();
  return buildInstructions(input.lang, input.addressName);
}

async function sleep(ms: number) {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

function withCors(response: Response) {
  const headers = new Headers(response.headers);
  headers.set("Access-Control-Allow-Origin", "*");
  headers.set("Access-Control-Allow-Headers", "Content-Type, Accept, X-Weronika-Lovable-Key");
  headers.set("Access-Control-Allow-Methods", "POST, OPTIONS");
  return new Response(response.body, { status: response.status, headers });
}

function jsonError(message: string, status: number) {
  return withCors(Response.json({ error: sanitizeGatewayMessage(message, status) }, { status }));
}

function readKey(request: Request) {
  const fromEnv = process.env["LOVABLE_API_KEY"]?.trim();
  if (fromEnv) return fromEnv;
  return request.headers.get("x-weronika-lovable-key")?.trim() || "";
}

async function postResponses(apiKey: string, body: unknown, signal: AbortSignal) {
  let lastResponse: Response | null = null;
  let lastError: unknown = null;
  for (let attempt = 0; attempt <= MAX_TRANSIENT_RETRIES; attempt++) {
    try {
      const response = await fetch(RESPONSES_URL, {
        method: "POST",
        signal,
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
          "Lovable-API-Key": apiKey,
          Authorization: `Bearer ${apiKey}`,
        },
        body: JSON.stringify(body),
      });
      if (response.ok || !isTransientStatus(response.status) || attempt === MAX_TRANSIENT_RETRIES) {
        return response;
      }
      lastResponse = response;
      await response.arrayBuffer().catch(() => undefined);
    } catch (error) {
      if (signal.aborted) throw error;
      lastError = error;
      if (attempt === MAX_TRANSIENT_RETRIES) throw error;
    }
    await sleep(280 * (attempt + 1));
  }
  if (lastResponse) return lastResponse;
  throw lastError instanceof Error ? lastError : new Error("The AI brain failed to respond");
}

async function postChatCompletions(
  apiKey: string,
  input: BrainInput,
  signal: AbortSignal,
  model: string,
) {
  return fetch(CHAT_COMPLETIONS_URL, {
    method: "POST",
    signal,
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
      "Lovable-API-Key": apiKey,
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model,
      stream: true,
      messages: [
        { role: "system", content: instructionsFor(input) },
        ...input.history,
        { role: "user", content: input.message },
      ],
    }),
  });
}

async function completeWithGateway(apiKey: string, input: BrainInput, signal: AbortSignal) {
  const gateway = createLovableAiGatewayProvider(apiKey);
  let lastError: unknown = null;
  for (const modelName of CHAT_MODELS) {
    try {
      const { text } = await generateText({
        model: gateway(modelName),
        system: instructionsFor(input),
        messages: [...input.history, { role: "user", content: input.message }],
        abortSignal: signal,
      });
      const reply = (text || "").trim();
      if (reply) return reply;
    } catch (error) {
      lastError = error;
      const statusCode = (error as { statusCode?: number }).statusCode;
      if (statusCode === 401 || statusCode === 402 || statusCode === 403 || statusCode === 429)
        throw error;
    }
  }
  throw lastError instanceof Error ? lastError : new Error("The AI brain failed to respond");
}

function sentenceChunks(reply: string) {
  const parts = reply.split(/(?<=[.!?])\s+/).filter(Boolean);
  return parts.length ? parts : [reply];
}

function streamTextReply(reply: string, model: string) {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const piece of sentenceChunks(reply)) {
        controller.enqueue(encoder.encode(sseEvent({ type: "delta", text: piece + " " })));
      }
      controller.enqueue(encoder.encode(sseEvent({ type: "done" })));
      controller.close();
    },
  });
  return withCors(
    new Response(stream, {
      status: 200,
      headers: {
        "Content-Type": "text/event-stream; charset=utf-8",
        "Cache-Control": "no-cache, no-transform",
        "X-Accel-Buffering": "no",
        "X-Weronika-Brain": model,
      },
    }),
  );
}

async function relayHosted(body: unknown, signal: AbortSignal) {
  let last: Response | null = null;
  let lastError: unknown = null;
  for (const origin of HOSTED_ORIGINS) {
    try {
      const relay = await fetch(`${origin}/api/public/brain`, {
        method: "POST",
        signal,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (relay.status === 401 || relay.status === 403 || relay.status === 404) {
        last = relay;
        continue;
      }
      const headers = new Headers();
      headers.set("Content-Type", relay.headers.get("content-type") ?? "application/json");
      headers.set("X-Weronika-Brain", "relay");
      return withCors(new Response(relay.body, { status: relay.status, headers }));
    } catch (error) {
      lastError = error;
    }
  }
  if (last) {
    const raw = await last.text();
    return jsonError(
      raw || "Could not reach the online Lovable brain",
      last.status === 404 ? 502 : last.status,
    );
  }
  const messageText =
    lastError instanceof Error ? lastError.message : "Could not reach the online Lovable brain";
  return jsonError(messageText, 502);
}

export const Route = createFileRoute("/api/public/brain")({
  server: {
    handlers: {
      OPTIONS: async () => withCors(new Response(null, { status: 204 })),
      POST: async ({ request }) => {
        let body: {
          message?: unknown;
          history?: unknown;
          lang?: unknown;
          addressName?: unknown;
          task?: unknown;
        };
        try {
          body = (await request.json()) as typeof body;
        } catch {
          return jsonError("Invalid JSON body", 400);
        }

        const message = typeof body.message === "string" ? body.message.trim() : "";
        if (!message) return jsonError("message is required", 400);
        if (message.length > 8000) return jsonError("message is too long", 400);

        const history = sanitizeHistory(body.history);
        const lang = sanitizeLang(body.lang, message);
        const addressName = sanitizeAddressName(body.addressName);
        const task = body.task === "media-intent" || body.task === "automation-plan"
          ? body.task
          : undefined;
        const input: BrainInput = {
          message,
          history,
          lang,
          addressName,
          ...(task ? { task } : {}),
        };
        const apiKey = readKey(request);

        if (!apiKey) {
          return relayHosted(input, request.signal);
        }

        try {
          const reply = await completeWithGateway(apiKey, input, request.signal);
          return streamTextReply(reply, CHAT_MODELS[0]);
        } catch (gatewayError) {
          const statusCode = (gatewayError as { statusCode?: number }).statusCode;
          if (
            statusCode === 401 ||
            statusCode === 402 ||
            statusCode === 403 ||
            statusCode === 429
          ) {
            const messageText =
              gatewayError instanceof Error
                ? gatewayError.message
                : "The AI brain failed to respond";
            return jsonError(messageText, statusCode);
          }
        }

        try {
          const payload = buildResponsesBody(input);
          let upstream = await postResponses(apiKey, payload, request.signal);
          if (upstream.status === 404 || upstream.status === 405) {
            await upstream.arrayBuffer().catch(() => undefined);
            upstream = await postChatCompletions(apiKey, input, request.signal, CHAT_MODELS[0]);
          }
          if (!upstream.ok) {
            const raw = await upstream.text();
            console.error(
              "brain error",
              upstream.status,
              sanitizeGatewayMessage(raw, upstream.status),
            );
            return jsonError(raw || "The AI brain failed to respond", upstream.status);
          }
          if (!upstream.body) return jsonError("The brain returned an empty reply", 502);

          const encoder = new TextEncoder();
          const stream = new ReadableStream<Uint8Array>({
            async start(controller) {
              let sent = false;
              const send = (chunk: string) => controller.enqueue(encoder.encode(chunk));
              try {
                await readResponseDeltas(
                  upstream.body as ReadableStream<Uint8Array>,
                  (text) => {
                    sent = true;
                    send(sseEvent({ type: "delta", text }));
                  },
                  (error) => {
                    send(sseEvent({ type: "error", error }));
                  },
                );
                if (!sent)
                  send(sseEvent({ type: "error", error: "The brain returned an empty reply" }));
                send(sseEvent({ type: "done" }));
              } catch (error) {
                const messageText =
                  error instanceof Error ? error.message : "The AI brain failed while streaming";
                send(sseEvent({ type: "error", error: sanitizeGatewayMessage(messageText) }));
                send(sseEvent({ type: "done" }));
              } finally {
                controller.close();
              }
            },
          });
          return withCors(
            new Response(stream, {
              status: 200,
              headers: {
                "Content-Type": "text/event-stream; charset=utf-8",
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
                "X-Weronika-Brain": "responses",
              },
            }),
          );
        } catch (error) {
          const messageText =
            error instanceof Error ? error.message : "The AI brain failed to respond";
          console.error("brain error", 502, sanitizeGatewayMessage(messageText));
          return jsonError(messageText, 502);
        }
      },
    },
  },
});
