import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const prompt = readFileSync(new URL("../src/lib/brain-stream.server.ts", import.meta.url), "utf8");
assert.match(prompt, /buildAutomationPlanInstructions/);
assert.match(prompt, /Return exactly one JSON object/);
assert.match(prompt, /Never plan an automatic send/);
assert.doesNotMatch(prompt, /Use intent "browser"/);
assert.match(prompt, /Use intent "write_code"/);
assert.match(prompt, /1 to 10 objects/);
assert.match(prompt, /JavaScript\/TypeScript/);
assert.match(prompt, /whatsapp, telegram, instagram, facebook \(Messenger\), or x/);

const brainRoute = readFileSync(
  new URL("../src/routes/api/public/brain.ts", import.meta.url),
  "utf8",
);
assert.match(brainRoute, /body\.task === "automation-plan"/);
assert.match(brainRoute, /buildAutomationPlanInstructions\(\)/);

const orb = readFileSync(new URL("../public/weronika.html", import.meta.url), "utf8");
assert.match(orb, /task: "automation-plan"/);
assert.match(orb, /\/api\/automation\/prepare/);
assert.match(orb, /\/api\/automation\/confirm/);
assert.match(orb, /\/api\/automation\/status/);
assert.match(orb, /function createOrbScene/);
assert.match(orb, /mountDeveloperTools\(\{/);
assert.match(orb, /onPrompt: async/);
assert.match(orb, /openDraftFiles/);
assert.match(orb, /id="blueprintOpenBtn"/);
assert.match(orb, /id="workspaceOpenBtn"/);
assert.match(orb, /BLUEPRINT MODE/);
assert.doesNotMatch(orb, /browser-addresses|open-websites|data-tab="browser"/);

const developerTools = readFileSync(
  new URL("../public/developer-tools.js", import.meta.url),
  "utf8",
);
assert.match(developerTools, /WORKSPACE/);
assert.match(developerTools, /BUILD CODE/);
assert.match(developerTools, /openDraftFiles/);
assert.match(developerTools, /RUN PYTHON/);
assert.doesNotMatch(developerTools, /BROWSER|browser-addresses|open-websites|browser\/open/);

const technical = readFileSync(new URL("../public/technical-viewer.js", import.meta.url), "utf8");
assert.match(technical, /openVRMFile/);
assert.match(technical, /openPhotoFile/);
assert.match(technical, /photo-relief/);
assert.match(orb, /shallow relief, not full reconstruction/);

console.log("cloud-brain to local-worker planner checks passed");
