const MAX_PROMPT_LENGTH = 6_000;

export async function rejectCloudMediaGeneration(
  kind: "image" | "song" | "video",
  request: Request,
) {
  let body: { prompt?: unknown };
  try {
    body = (await request.json()) as { prompt?: unknown };
  } catch {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const prompt = typeof body.prompt === "string" ? body.prompt.trim() : "";
  if (!prompt) return Response.json({ error: "prompt is required" }, { status: 400 });
  if (prompt.length > MAX_PROMPT_LENGTH) {
    return Response.json(
      { error: `prompt is too long (maximum ${MAX_PROMPT_LENGTH} characters)` },
      { status: 400 },
    );
  }

  return Response.json(
    {
      error: `Cloud ${kind} generation is disabled. Ask Weronika for a local prompt and use a generator installed on this PC.`,
    },
    { status: 501 },
  );
}

export function rejectCloudMediaStatus() {
  return Response.json(
    { error: "Cloud video generation is disabled. Use the local video-prompt workflow instead." },
    { status: 501 },
  );
}
