import { createFileRoute } from "@tanstack/react-router";

import { GATEWAY, gatewayFetch, getApiKey, relayJson } from "@/lib/relay.server";

// A song = AI-written lyrics performed by an expressive singing voice.
export const Route = createFileRoute("/api/public/song")({
  server: {
    handlers: {
      POST: async ({ request }) => {
        let body: { prompt?: unknown };
        try {
          body = (await request.json()) as { prompt?: unknown };
        } catch {
          return Response.json({ error: "Invalid JSON body" }, { status: 400 });
        }
        const prompt = typeof body.prompt === "string" ? body.prompt.trim() : "";
        if (!prompt) return Response.json({ error: "prompt is required" }, { status: 400 });

        const apiKey = getApiKey();
        if (!apiKey) return relayJson("/api/public/song", { method: "POST", body: { prompt } });

        try {
          // 1. Write the lyrics, in the same language the request used.
          const lyricsRes = await gatewayFetch(apiKey, "/chat/completions", {
            model: "google/gemini-3.7-flash",
            messages: [
              {
                role: "system",
                content:
                  "You write short original song lyrics. Reply with lyrics only — no title, no markdown, no notes. Two short verses and a repeated chorus, about 12 lines total. Write in the same language the user used.",
              },
              { role: "user", content: prompt },
            ],
          });
          if (!lyricsRes.ok) {
            const err = (await lyricsRes.json().catch(() => null)) as { message?: string } | null;
            return Response.json(
              { error: err?.message ?? "Song writing failed" },
              { status: lyricsRes.status },
            );
          }
          const lyricsJson = (await lyricsRes.json()) as {
            choices?: { message?: { content?: string } }[];
          };
          const lyrics = (lyricsJson.choices?.[0]?.message?.content ?? "").trim();
          if (!lyrics) return Response.json({ error: "No lyrics were written" }, { status: 502 });

          // 2. Perform them.
          const audioRes = await fetch(`${GATEWAY}/audio/speech`, {
            method: "POST",
            headers: {
              Authorization: `Bearer ${apiKey}`,
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              model: "openai/gpt-4o-mini-tts",
              voice: "shimmer",
              input: lyrics,
              instructions:
                "Sing these lyrics melodically with a warm pop voice, clear rhythm, emotional phrasing and gentle vibrato. Keep a steady tempo like a real song, not like reading.",
            }),
          });
          if (!audioRes.ok) {
            const text = await audioRes.text().catch(() => "");
            return Response.json(
              { error: text || "Singing failed" },
              { status: audioRes.status },
            );
          }
          const bytes = new Uint8Array(await audioRes.arrayBuffer());
          let binary = "";
          for (let i = 0; i < bytes.length; i += 0x8000) {
            binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
          }
          const b64 = btoa(binary);
          return Response.json({ audio: `data:audio/mpeg;base64,${b64}`, lyrics });
        } catch (error) {
          const message = error instanceof Error ? error.message : "Song generation failed";
          return Response.json({ error: message }, { status: 502 });
        }
      },
    },
  },
});
