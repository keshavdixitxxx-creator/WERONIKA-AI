import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const prompt = readFileSync(new URL("../src/lib/brain-stream.server.ts", import.meta.url), "utf8");
assert.match(prompt, /buildAutomationPlanInstructions/);
assert.match(prompt, /Return exactly one JSON object/);
assert.match(prompt, /Never plan an automatic send/);
assert.match(prompt, /whatsapp, telegram, instagram, facebook \(Messenger\), or x/);

const brainRoute = readFileSync(new URL("../src/routes/api/public/brain.ts", import.meta.url), "utf8");
assert.match(brainRoute, /body\.task === "automation-plan"/);
assert.match(brainRoute, /buildAutomationPlanInstructions\(\)/);

const orb = readFileSync(new URL("../public/weronika.html", import.meta.url), "utf8");
assert.match(orb, /task: "automation-plan"/);
assert.match(orb, /\/api\/automation\/prepare/);
assert.match(orb, /\/api\/automation\/confirm/);
assert.match(orb, /\/api\/automation\/status/);
assert.match(orb, /function createOrbScene/);

console.log("cloud-brain to local-worker planner checks passed");
