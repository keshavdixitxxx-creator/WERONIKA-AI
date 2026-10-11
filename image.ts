import { createFileRoute } from "@tanstack/react-router";

import { gatewayFetch, getApiKey, relayJson } from "@/lib/relay.server";

export const Route = createFileRoute("/api/public/image")({
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
        if (!apiKey) return relayJson("/api/public/image", { method: "POST", body: { prompt } });

        try {
          const res = await gatewayFetch(apiKey, "/images/generations", {
            model: "google/gemini-3-pro-image",
            messages: [{ role: "user", content: prompt }],
            modalities: ["image", "text"],
          });
          if (!res.ok) {
            const err = (await res.json().catch(() => null)) as { message?: string } | null;
            return Response.json(
              { error: err?.message ?? "Image generation failed" },
              { status: res.status },
            );
          }
          const json = (await res.json()) as { data?: { b64_json?: string }[] };
          const b64 = json.data?.[0]?.b64_json;
          if (!b64) return Response.json({ error: "No image was returned" }, { status: 502 });
          return Response.json({ image: `data:image/png;base64,${b64}`, prompt });
        } catch (error) {
          const message = error instanceof Error ? error.message : "Image generation failed";
          return Response.json({ error: message }, { status: 502 });
        }
      },
    },
  },
});
