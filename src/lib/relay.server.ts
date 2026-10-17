// Server-only helper.
//
// When the app runs on Lovable, LOVABLE_API_KEY is present and every AI call
// goes straight to the AI Gateway. When somebody downloads the code and runs
// `npm install && npm run dev` on their own machine there is no key, so the
// same endpoints transparently relay the request to the hosted copy of this
// app. That is what makes the local build answer exactly like the online one
// with zero setup.

export const HOSTED_ORIGINS = [
  "https://weronika-ai.lovable.app",
  "https://project--9b370ba5-6b95-4715-86da-780c9e2c7e13-dev.lovable.app",
];

export const HOSTED_ORIGIN = HOSTED_ORIGINS[0];

export const GATEWAY = "https://ai.gateway.lovable.dev/v1";

export function getApiKey(): string | undefined {
  const key = process.env["LOVABLE_API_KEY"];
  return key && key.trim() ? key : undefined;
}

export function gatewayErrorMessage(value: unknown, fallback: string): string {
  const clean = (message: string) =>
    message
      .replace(
        /(?:sk-[A-Za-z0-9_-]{8,}|lovable_[A-Za-z0-9_-]{8,}|Bearer\s+[A-Za-z0-9._-]{8,})/gi,
        "[redacted]",
      )
      .replace(/\s+/g, " ")
      .trim()
      .slice(0, 280);
  if (typeof value === "string" && value.trim()) return clean(value);
  if (!value || typeof value !== "object") return fallback;
  const body = value as { error?: unknown; message?: unknown };
  if (typeof body.error === "string" && body.error.trim()) return clean(body.error);
  if (body.error && typeof body.error === "object") {
    const nestedMessage = (body.error as { message?: unknown }).message;
    if (typeof nestedMessage === "string" && nestedMessage.trim()) return clean(nestedMessage);
  }
  return typeof body.message === "string" && body.message.trim() ? clean(body.message) : fallback;
}

export async function relayJson(
  path: string,
  init: { method: "GET" | "POST"; body?: unknown },
): Promise<Response> {
  const requestInit: RequestInit = { method: init.method, signal: AbortSignal.timeout(8000) };
  if (init.body !== undefined) {
    requestInit.headers = { "Content-Type": "application/json" };
    requestInit.body = JSON.stringify(init.body);
  }
  let last: Response | null = null;
  let lastError: unknown = null;
  for (const origin of HOSTED_ORIGINS) {
    try {
      const res = await fetch(`${origin}${path}`, requestInit);
      if (res.status === 401 || res.status === 403 || res.status === 404) {
        last = res;
        continue;
      }
      const text = await res.text();
      return new Response(text, {
        status: res.status,
        headers: { "Content-Type": res.headers.get("content-type") ?? "application/json" },
      });
    } catch (error) {
      lastError = error;
    }
  }
  if (last) {
    const text = await last.text();
    return new Response(text, {
      status: last.status,
      headers: { "Content-Type": last.headers.get("content-type") ?? "application/json" },
    });
  }
  const message =
    lastError instanceof Error ? lastError.message : "Could not reach the online brain";
  return Response.json({ error: message }, { status: 502 });
}

export function gatewayFetch(apiKey: string, path: string, body: unknown) {
  return fetch(`${GATEWAY}${path}`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Lovable-API-Key": apiKey,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
}
