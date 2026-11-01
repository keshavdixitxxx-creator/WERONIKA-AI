import { randomBytes, timingSafeEqual } from "node:crypto";

const GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth";
const GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token";
const GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me";
const SESSION_COOKIE = "weronika_gmail_session";
const STATE_COOKIE = "weronika_gmail_oauth_state";
const SESSION_TTL_MS = 55 * 60 * 1000;
const STATE_TTL_MS = 10 * 60 * 1000;
const MAX_BODY_CHARS = 24_000;

type GmailSession = { accessToken: string; expiresAt: number };
type OAuthState = { browserNonce: string; expiresAt: number };
type PreparedSend = {
  recipient: string;
  body: string;
  threadId: string;
  subject: string;
  inReplyTo: string;
  references: string;
  expiresAt: number;
};

// Intentionally process-memory only: no Gmail token or email content is written to disk/database.
// Deployments must use a single persistent app process for the duration of a session.
const sessions = new Map<string, GmailSession>();
const states = new Map<string, OAuthState>();
const preparedSends = new Map<string, PreparedSend>();

function env(name: string): string {
  return String(process.env[name] || "").trim();
}

function credentials() {
  const clientId = env("GOOGLE_OAUTH_CLIENT_ID");
  const clientSecret = env("GOOGLE_OAUTH_CLIENT_SECRET");
  const redirectUri = env("GOOGLE_OAUTH_REDIRECT_URI");
  let parsedRedirect: URL | null = null;
  try {
    parsedRedirect = new URL(redirectUri);
  } catch {
    /* checked below */
  }
  const secureRedirect =
    parsedRedirect?.protocol === "https:" ||
    (parsedRedirect?.protocol === "http:" &&
      ["localhost", "127.0.0.1"].includes(parsedRedirect.hostname));
  if (
    !clientId ||
    !clientSecret ||
    !parsedRedirect ||
    !secureRedirect ||
    parsedRedirect.username ||
    parsedRedirect.password ||
    parsedRedirect.pathname !== "/api/gmail/callback" ||
    parsedRedirect.search ||
    parsedRedirect.hash
  ) {
    throw new Error(
      "Gmail OAuth is not configured. Set GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET, and a valid GOOGLE_OAUTH_REDIRECT_URI.",
    );
  }
  return { clientId, clientSecret, redirectUri: parsedRedirect.toString() };
}

function cookieOptions(request: Request, maxAge: number) {
  const secure = new URL(request.url).protocol === "https:";
  return `Path=/; HttpOnly; SameSite=Lax; Max-Age=${maxAge}${secure ? "; Secure" : ""}`;
}

function getCookie(request: Request, key: string): string | null {
  const cookie = request.headers.get("cookie") || "";
  for (const part of cookie.split(";")) {
    const index = part.indexOf("=");
    if (index > -1 && part.slice(0, index).trim() === key) {
      try {
        return decodeURIComponent(part.slice(index + 1).trim());
      } catch {
        return null;
      }
    }
  }
  return null;
}

function sameOriginPost(request: Request): boolean {
  const origin = request.headers.get("origin");
  return Boolean(origin && origin === new URL(request.url).origin);
}

function safeEqual(a: string, b: string): boolean {
  const aa = Buffer.from(a);
  const bb = Buffer.from(b);
  return aa.length === bb.length && timingSafeEqual(aa, bb);
}

function cleanExpired() {
  const now = Date.now();
  for (const [key, value] of sessions) if (value.expiresAt <= now) sessions.delete(key);
  for (const [key, value] of states) if (value.expiresAt <= now) states.delete(key);
  for (const [key, value] of preparedSends) if (value.expiresAt <= now) preparedSends.delete(key);
}

function sessionFor(request: Request): { id: string; session: GmailSession } | null {
  cleanExpired();
  const id = getCookie(request, SESSION_COOKIE);
  const session = id ? sessions.get(id) : undefined;
  if (!id || !session || session.expiresAt <= Date.now()) return null;
  return { id, session };
}

export function gmailOAuthConfigured() {
  try {
    credentials();
    return true;
  } catch {
    return false;
  }
}

export function startGmailOAuth(request: Request): Response {
  try {
    const { clientId, redirectUri } = credentials();
    const url = new URL(request.url);
    if (url.origin !== new URL(redirectUri).origin)
      return Response.json(
        { error: "Gmail OAuth origin does not match the configured redirect URI." },
        { status: 400 },
      );
    cleanExpired();
    if (states.size >= 256) states.delete(states.keys().next().value as string);
    const state = randomBytes(32).toString("base64url");
    const browserNonce = randomBytes(32).toString("base64url");
    states.set(state, { browserNonce, expiresAt: Date.now() + STATE_TTL_MS });
    const authorize = new URL(GOOGLE_AUTH_URL);
    authorize.search = new URLSearchParams({
      client_id: clientId,
      redirect_uri: redirectUri,
      response_type: "code",
      scope:
        "https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.send",
      access_type: "online",
      include_granted_scopes: "true",
      state,
      prompt: "consent",
    }).toString();
    return new Response(null, {
      status: 302,
      headers: {
        Location: authorize.toString(),
        "Cache-Control": "no-store",
        "Set-Cookie": `${STATE_COOKIE}=${encodeURIComponent(browserNonce)}; ${cookieOptions(request, 600)}`,
      },
    });
  } catch (error) {
    return Response.json(
      { error: error instanceof Error ? error.message : "Gmail OAuth unavailable" },
      { status: 503 },
    );
  }
}

export async function completeGmailOAuth(request: Request): Promise<Response> {
  const url = new URL(request.url);
  const state = url.searchParams.get("state") || "";
  const code = url.searchParams.get("code") || "";
  const entry = states.get(state);
  states.delete(state);
  const browserNonce = getCookie(request, STATE_COOKIE) || "";
  if (!entry || entry.expiresAt < Date.now() || !safeEqual(entry.browserNonce, browserNonce)) {
    return new Response("Gmail authorization could not be verified. Please try connecting again.", {
      status: 400,
      headers: { "Cache-Control": "no-store" },
    });
  }
  if (!code || url.searchParams.has("error")) {
    return new Response(
      "Gmail authorization was cancelled. You can close this page and try again.",
      { status: 400, headers: { "Cache-Control": "no-store" } },
    );
  }
  try {
    const { clientId, clientSecret, redirectUri } = credentials();
    if (url.origin !== new URL(redirectUri).origin)
      return new Response("Gmail OAuth origin does not match the configured redirect URI.", {
        status: 400,
        headers: { "Cache-Control": "no-store" },
      });
    const tokenResponse = await fetch(GOOGLE_TOKEN_URL, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        code,
        client_id: clientId,
        client_secret: clientSecret,
        redirect_uri: redirectUri,
        grant_type: "authorization_code",
      }),
      signal: AbortSignal.timeout(12_000),
    });
    const tokens = (await tokenResponse.json()) as { access_token?: string; expires_in?: number };
    if (!tokenResponse.ok || !tokens.access_token)
      throw new Error("Google did not return an access token.");
    cleanExpired();
    const sessionId = randomBytes(32).toString("base64url");
    const lifetime = Math.max(
      60,
      Math.min(Number(tokens.expires_in) || 3600, SESSION_TTL_MS / 1000),
    );
    sessions.set(sessionId, {
      accessToken: tokens.access_token,
      expiresAt: Date.now() + lifetime * 1000,
    });
    const headers = new Headers({
      Location: `${url.origin}/weronika.html?gmail=connected`,
      "Cache-Control": "no-store",
    });
    headers.append(
      "Set-Cookie",
      `${SESSION_COOKIE}=${encodeURIComponent(sessionId)}; ${cookieOptions(request, lifetime)}`,
    );
    headers.append("Set-Cookie", `${STATE_COOKIE}=; ${cookieOptions(request, 0)}`);
    return new Response(null, { status: 302, headers });
  } catch {
    return new Response("Gmail could not be connected. Please try again.", {
      status: 502,
      headers: { "Cache-Control": "no-store" },
    });
  }
}

export function gmailStatus(request: Request): Response {
  const active = sessionFor(request);
  return Response.json(
    { configured: gmailOAuthConfigured(), connected: Boolean(active) },
    { headers: { "Cache-Control": "no-store" } },
  );
}

export function disconnectGmail(request: Request): Response {
  if (!sameOriginPost(request))
    return Response.json(
      { error: "Cross-origin Gmail requests are not allowed." },
      { status: 403 },
    );
  const active = sessionFor(request);
  if (active) sessions.delete(active.id);
  return Response.json(
    { connected: false },
    {
      headers: {
        "Cache-Control": "no-store",
        "Set-Cookie": `${SESSION_COOKIE}=; ${cookieOptions(request, 0)}`,
      },
    },
  );
}

async function gmailFetch(request: Request, path: string, init?: RequestInit): Promise<Response> {
  const active = sessionFor(request);
  if (!active)
    return Response.json(
      { error: "Connect Gmail again to continue; this app keeps access tokens only in memory." },
      { status: 401 },
    );
  const response = await fetch(`${GMAIL_API}${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${active.session.accessToken}`, ...(init?.headers || {}) },
    signal: AbortSignal.timeout(15_000),
  });
  if (response.status === 401) sessions.delete(active.id);
  return response;
}

export async function listGmailMessages(request: Request): Promise<Response> {
  try {
    const url = new URL(request.url);
    const query = (url.searchParams.get("q") || "in:inbox").slice(0, 300);
    const list = await gmailFetch(
      request,
      `/messages?maxResults=25&q=${encodeURIComponent(query)}`,
    );
    if (!list.ok)
      return Response.json(
        {
          error:
            list.status === 401
              ? "Gmail session expired. Reconnect to continue."
              : "Gmail messages could not be loaded.",
        },
        { status: list.status },
      );
    const data = (await list.json()) as {
      messages?: Array<{ id: string; threadId: string }>;
      resultSizeEstimate?: number;
    };
    const messages = await Promise.all(
      (data.messages || []).slice(0, 25).map(async ({ id, threadId }) => {
        const params = new URLSearchParams({ format: "metadata" });
        for (const name of ["From", "To", "Subject", "Date"])
          params.append("metadataHeaders", name);
        const itemResponse = await gmailFetch(
          request,
          `/messages/${encodeURIComponent(id)}?${params}`,
        );
        if (!itemResponse.ok) return null;
        const item = (await itemResponse.json()) as GmailMessage;
        return {
          id,
          threadId,
          snippet: String(item.snippet || "").slice(0, 400),
          from: header(item, "From"),
          to: header(item, "To"),
          subject: header(item, "Subject"),
          date: header(item, "Date"),
        };
      }),
    );
    return Response.json(
      { messages: messages.filter(Boolean), resultSizeEstimate: data.resultSizeEstimate || 0 },
      { headers: { "Cache-Control": "no-store" } },
    );
  } catch {
    return Response.json({ error: "Gmail messages could not be loaded." }, { status: 502 });
  }
}

type GmailMessage = {
  id?: string;
  threadId?: string;
  snippet?: string;
  payload?: {
    headers?: Array<{ name: string; value: string }>;
    mimeType?: string;
    body?: { data?: string };
    parts?: GmailMessage["payload"][];
  };
};
function header(message: GmailMessage, name: string) {
  return String(
    message.payload?.headers?.find((value) => value.name.toLowerCase() === name.toLowerCase())
      ?.value || "",
  ).slice(0, 500);
}
function parseMessageIds(value: string): string[] {
  return (value.match(/<[^<>\s]{1,250}>/g) || []).slice(-20);
}
function collectMimeText(part: GmailMessage["payload"], mimeType: string): string[] {
  if (!part) return [];
  const nested = part.parts?.flatMap((child) => collectMimeText(child, mimeType)) || [];
  if (nested.length) return nested;
  if (part.mimeType !== mimeType || !part.body?.data) return [];
  try {
    return [
      Buffer.from(part.body.data.replace(/-/g, "+").replace(/_/g, "/"), "base64").toString("utf8"),
    ];
  } catch {
    return [];
  }
}
function decodePart(part: GmailMessage["payload"]): string {
  const plain = collectMimeText(part, "text/plain").join("\n");
  if (plain) return plain;
  return collectMimeText(part, "text/html")
    .join("\n")
    .replace(/<(script|style)\b[^>]*>[\s\S]*?<\/\1>/gi, " ")
    .replace(/<br\s*\/?\s*>|<\/(?:p|div|li|tr)>/gi, "\n")
    .replace(/<[^>]*>/g, " ")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&quot;/gi, '"')
    .replace(/&#39;|&apos;/gi, "'")
    .replace(/[ \t]+/g, " ")
    .trim();
}

export async function getGmailMessage(request: Request, messageId: string): Promise<Response> {
  if (!/^[a-zA-Z0-9_-]{1,200}$/.test(messageId))
    return Response.json({ error: "Invalid message ID." }, { status: 400 });
  try {
    const response = await gmailFetch(
      request,
      `/messages/${encodeURIComponent(messageId)}?format=full`,
    );
    if (!response.ok)
      return Response.json(
        {
          error:
            response.status === 401
              ? "Gmail session expired. Reconnect to continue."
              : "The selected message could not be read.",
        },
        { status: response.status },
      );
    const message = (await response.json()) as GmailMessage;
    const body = decodePart(message.payload) || String(message.snippet || "");
    return Response.json(
      {
        id: message.id,
        threadId: message.threadId,
        from: header(message, "From"),
        to: header(message, "To"),
        subject: header(message, "Subject"),
        date: header(message, "Date"),
        snippet: String(message.snippet || "").slice(0, 500),
        body: body.slice(0, MAX_BODY_CHARS),
      },
      { headers: { "Cache-Control": "no-store" } },
    );
  } catch {
    return Response.json({ error: "The selected message could not be read." }, { status: 502 });
  }
}

export async function prepareGmailSend(request: Request): Promise<Response> {
  if (!sameOriginPost(request))
    return Response.json(
      { error: "Cross-origin Gmail requests are not allowed." },
      { status: 403 },
    );
  const active = sessionFor(request);
  if (!active)
    return Response.json({ error: "Reconnect Gmail before preparing a reply." }, { status: 401 });
  try {
    const input = (await request.json()) as {
      recipient?: unknown;
      body?: unknown;
      messageId?: unknown;
    };
    const recipient = typeof input.recipient === "string" ? input.recipient.trim() : "";
    const body = typeof input.body === "string" ? input.body.trim() : "";
    const messageId = typeof input.messageId === "string" ? input.messageId : "";
    if (
      recipient.length > 320 ||
      /[,;\r\n]/.test(recipient) ||
      !/^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$/.test(recipient) ||
      !body ||
      body.length > 12_000 ||
      !/^[a-zA-Z0-9_-]{1,200}$/.test(messageId)
    )
      return Response.json(
        {
          error:
            "Choose one valid recipient, a selected source message, and a reply under 12,000 characters.",
        },
        { status: 400 },
      );
    const sourceResponse = await gmailFetch(
      request,
      `/messages/${encodeURIComponent(messageId)}?format=metadata&metadataHeaders=Subject&metadataHeaders=Message-ID&metadataHeaders=References`,
    );
    if (!sourceResponse.ok)
      return Response.json(
        { error: "The selected source message could not be verified." },
        { status: sourceResponse.status },
      );
    const source = (await sourceResponse.json()) as GmailMessage;
    const threadId = String(source.threadId || "");
    if (!/^[a-zA-Z0-9_-]{1,200}$/.test(threadId))
      return Response.json(
        { error: "The selected message has no valid Gmail thread." },
        { status: 400 },
      );
    const sourceMessageId = parseMessageIds(header(source, "Message-ID")).at(-1) || "";
    const references = [
      ...new Set(
        [...parseMessageIds(header(source, "References")), sourceMessageId].filter(Boolean),
      ),
    ]
      .slice(-20)
      .join(" ");
    const sourceSubject = Array.from(header(source, "Subject"), (character) => {
      const code = character.charCodeAt(0);
      return code < 32 || code === 127 ? " " : character;
    })
      .join("")
      .trim()
      .slice(0, 400);
    const subject = /^re\s*:/i.test(sourceSubject)
      ? sourceSubject
      : `Re: ${sourceSubject || "(no subject)"}`;
    const confirmationToken = randomBytes(24).toString("base64url");
    preparedSends.set(confirmationToken, {
      recipient,
      body,
      threadId,
      subject,
      inReplyTo: sourceMessageId,
      references,
      expiresAt: Date.now() + 10 * 60 * 1000,
    });
    return Response.json(
      { confirmationToken, recipient, body, expiresInSeconds: 600 },
      { headers: { "Cache-Control": "no-store" } },
    );
  } catch {
    return Response.json({ error: "The reply could not be prepared." }, { status: 400 });
  }
}

export async function sendPreparedGmailReply(request: Request): Promise<Response> {
  if (!sameOriginPost(request))
    return Response.json(
      { error: "Cross-origin Gmail requests are not allowed." },
      { status: 403 },
    );
  const active = sessionFor(request);
  if (!active) return Response.json({ error: "Reconnect Gmail before sending." }, { status: 401 });
  try {
    const input = (await request.json()) as {
      confirmationToken?: unknown;
      recipient?: unknown;
      body?: unknown;
      confirm?: unknown;
    };
    const token = typeof input.confirmationToken === "string" ? input.confirmationToken : "";
    const prepared = preparedSends.get(token);
    if (!prepared || prepared.expiresAt <= Date.now())
      return Response.json(
        { error: "This reviewed reply expired. Prepare and review it again." },
        { status: 409 },
      );
    if (
      input.confirm !== true ||
      input.recipient !== prepared.recipient ||
      input.body !== prepared.body
    )
      return Response.json(
        { error: "The recipient or message differs from the reviewed draft. Nothing was sent." },
        { status: 409 },
      );
    preparedSends.delete(token);
    const encodedSubject = `=?UTF-8?B?${Buffer.from(prepared.subject, "utf8").toString("base64")}?=`;
    const raw = [
      `To: ${prepared.recipient}`,
      `Subject: ${encodedSubject}`,
      ...(prepared.inReplyTo ? [`In-Reply-To: ${prepared.inReplyTo}`] : []),
      ...(prepared.references ? [`References: ${prepared.references}`] : []),
      "MIME-Version: 1.0",
      "Content-Type: text/plain; charset=UTF-8",
      "Content-Transfer-Encoding: 8bit",
      "",
      prepared.body,
    ].join("\r\n");
    const response = await gmailFetch(request, "/messages/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        raw: Buffer.from(raw, "utf8").toString("base64url"),
        threadId: prepared.threadId,
      }),
    });
    if (!response.ok)
      return Response.json(
        {
          error:
            response.status === 401
              ? "Gmail session expired. Reconnect before sending."
              : "Gmail did not send the reviewed reply.",
        },
        { status: response.status },
      );
    const sent = (await response.json()) as { id?: string; threadId?: string };
    return Response.json(
      { sent: true, id: sent.id, threadId: sent.threadId },
      { headers: { "Cache-Control": "no-store" } },
    );
  } catch {
    return Response.json({ error: "Gmail could not send the reviewed reply." }, { status: 502 });
  }
}
