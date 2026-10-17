import { createOpenAICompatible } from "@ai-sdk/openai-compatible";

// Server-only helper: builds an AI SDK provider pointed at the Lovable AI
// Gateway. The gateway authenticates via the Lovable-API-Key header.
export function createLovableAiGatewayProvider(apiKey: string) {
  return createOpenAICompatible({
    name: "lovable-ai-gateway",
    baseURL: "https://ai.gateway.lovable.dev/v1",
    headers: {
      "Lovable-API-Key": apiKey,
    },
  });
}
