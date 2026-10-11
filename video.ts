import { createFileRoute } from "@tanstack/react-router";

import { GATEWAY, getApiKey, relayJson } from "@/lib/relay.server";

// POST { prompt }        -> { id }               (starts the job)
// GET  ?id=video_xxx     -> { status, video? }   (poll until completed)
export const Route = createFileRoute("/api/public/video")({
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
        if (!apiKey) return relayJson("/api/public/video", { method: "POST", body: { prompt } });

        const res = await fetch(`${GATEWAY}/videos`, {
          method: "POST",
          headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" },
          body: JSON.stringify({
            model: "google/gemini-omni-1.1-flash",
            input: prompt,
            response_format: { type: "video", resolution: "720p", duration: "6s" },
          }),
        });
        const json = (await res.json().catch(() => null)) as
          | { id?: string; message?: string }
          | null;
        if (!res.ok || !json?.id) {
          return Response.json(
            { error: json?.message ?? "Video generation failed" },
            { status: res.ok ? 502 : res.status },
          );
        }
        return Response.json({ id: json.id, status: "in_progress" });
      },

      GET: async ({ request }) => {
        const id = new URL(request.url).searchParams.get("id");
        if (!id) return Response.json({ error: "id is required" }, { status: 400 });

        const apiKey = getApiKey();
        if (!apiKey) {
          return relayJson(`/api/public/video?id=${encodeURIComponent(id)}`, { method: "GET" });
        }

        const jobRes = await fetch(`${GATEWAY}/videos/${id}`, {
          headers: { Authorization: `Bearer ${apiKey}` },
        });
        const job = (await jobRes.json().catch(() => null)) as
          | { status?: string; progress?: number; error?: { message?: string } }
          | null;
        if (!jobRes.ok || !job) {
          return Response.json({ error: "Could not check the video" }, { status: 502 });
        }
        if (job.status === "failed") {
          return Response.json(
            { status: "failed", error: job.error?.message ?? "Video generation failed" },
            { status: 200 },
          );
        }
        if (job.status !== "completed") {
          return Response.json({ status: job.status ?? "in_progress", progress: job.progress ?? 0 });
        }

        const contentRes = await fetch(`${GATEWAY}/videos/${id}/content`, {
          headers: { Authorization: `Bearer ${apiKey}` },
        });
        if (!contentRes.ok) {
          return Response.json({ error: "Could not download the video" }, { status: 502 });
        }
        const bytes = new Uint8Array(await contentRes.arrayBuffer());
        let binary = "";
        for (let i = 0; i < bytes.length; i += 0x8000) {
          binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
        }
        return Response.json({ status: "completed", video: `data:video/mp4;base64,${btoa(binary)}` });
      },
    },
  },
});
