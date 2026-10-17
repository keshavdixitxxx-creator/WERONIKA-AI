import { createFileRoute } from "@tanstack/react-router";

// Server-side proxy for DuckDuckGo's Instant Answer API. The orb page calls
// this as a factual-lookup fallback when the AI brain is unavailable, and
// calling it server-side avoids browser CORS limits.
type DdgTopic = { Text?: string; FirstURL?: string; Topics?: DdgTopic[] };

export const Route = createFileRoute("/api/public/answer")({
  server: {
    handlers: {
      GET: async ({ request }) => {
        const q = (new URL(request.url).searchParams.get("q") || "").trim();
        if (!q) {
          return Response.json({ error: "q is required" }, { status: 400 });
        }

        try {
          const res = await fetch(
            `https://api.duckduckgo.com/?q=${encodeURIComponent(q)}&format=json&no_html=1&skip_disambig=1`,
            { headers: { "User-Agent": "WeronikaAI/1.0" } },
          );
          if (!res.ok) {
            return Response.json({ error: "Answer lookup failed" }, { status: 502 });
          }

          const data = (await res.json()) as {
            AbstractText?: string;
            AbstractURL?: string;
            Answer?: string;
            RelatedTopics?: DdgTopic[];
          };

          let answer = (data.AbstractText || data.Answer || "").trim();
          let url = data.AbstractURL || "";

          if (!answer && Array.isArray(data.RelatedTopics)) {
            for (const topic of data.RelatedTopics) {
              const flat: DdgTopic | undefined = topic.Text
                ? topic
                : topic.Topics?.find((t) => t.Text);
              if (flat?.Text) {
                answer = flat.Text.trim();
                url = flat.FirstURL || "";
                break;
              }
            }
          }

          if (!answer) {
            return Response.json({ answer: null });
          }
          return Response.json({ answer, source: "DuckDuckGo", url });
        } catch (error) {
          console.error("answer lookup error", error);
          return Response.json({ error: "Answer lookup failed" }, { status: 502 });
        }
      },
    },
  },
});
