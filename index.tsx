import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Weronika AI — Holographic Orb Assistant" },
      {
        name: "description",
        content:
          "Talk with Weronika AI, a holographic orb assistant that holds natural conversations in any language, answers questions, and responds to voice and hand gestures.",
      },
      { property: "og:title", content: "Weronika AI — Holographic Orb Assistant" },
      {
        property: "og:description",
        content:
          "A holographic orb assistant that converses naturally in any language, with voice chat, hand-gesture control, and live answers.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

function Index() {
  // The orb experience is a self-contained page (public/weronika.html) — its
  // UI, orb scene, and settings code are intentionally left untouched. It is
  // embedded full-screen so / serves the app directly.
  return (
    <iframe
      src="/weronika.html"
      title="Weronika AI holographic orb assistant"
      allow="camera; microphone; autoplay; fullscreen"
      className="fixed inset-0 h-full w-full border-0"
    />
  );
}
