import assert from "node:assert/strict";
import {
  rejectCloudMediaGeneration,
  rejectCloudMediaStatus,
} from "./src/lib/local-media-only.server.ts";

const realFetch = globalThis.fetch;
globalThis.fetch = async () => {
  throw new Error("media routes must never make network requests");
};

try {
  const missingPrompt = await rejectCloudMediaGeneration(
    "image",
    new Request("http://localhost/api/public/image", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({}),
    }),
  );
  assert.equal(missingPrompt.status, 400);

  for (const kind of ["image", "song", "video"]) {
    const response = await rejectCloudMediaGeneration(
      kind,
      new Request(`http://localhost/api/public/${kind}`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ prompt: "a calm ocean at sunset" }),
      }),
    );
    assert.equal(response.status, 501);
    assert.match((await response.json()).error, /disabled/i);
  }

  assert.equal(rejectCloudMediaStatus().status, 501);
} finally {
  globalThis.fetch = realFetch;
}

console.log("local-only media route checks passed");
