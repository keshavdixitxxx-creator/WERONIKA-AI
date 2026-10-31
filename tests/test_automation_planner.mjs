import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const prompt = readFileSync(new URL("../src/lib/brain-stream.server.ts", import.meta.url), "utf8");
assert.match(prompt, /buildAutomationPlanInstructions/);
assert.match(prompt, /Return exactly one JSON object/);
assert.match(prompt, /Never plan an automatic send/);
assert.match(prompt, /Use intent "browser"/);
assert.match(prompt, /Use intent "write_code"/);
assert.match(prompt, /localhost ports/);
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
assert.match(orb, /mountDeveloperTools/);
assert.match(orb, /openDraftFile/);
const developerTools = readFileSync(
  new URL("../public/developer-tools.js", import.meta.url),
  "utf8",
);
assert.match(developerTools, /\/api\/workspace\/browser\/open/);
assert.match(developerTools, /WORKSPACE/);
assert.match(developerTools, /RUN PYTHON/);
assert.match(orb, /techVrmUpload/);
assert.match(orb, /techPhotoUpload/);
assert.match(orb, /BLUEPRINT MODE/);
const technical = readFileSync(new URL("../public/technical-viewer.js", import.meta.url), "utf8");
assert.match(technical, /openVRMFile/);
assert.match(technical, /openPhotoFile/);
assert.match(technical, /photo-relief/);
assert.match(orb, /shallow relief, not full reconstruction/);

console.log("cloud-brain to local-worker planner checks passed");
