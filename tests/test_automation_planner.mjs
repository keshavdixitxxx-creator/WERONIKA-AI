import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createStoredZip } from "../public/developer-tools.js";

const prompt = readFileSync(new URL("../src/lib/brain-stream.server.ts", import.meta.url), "utf8");
assert.match(prompt, /buildAutomationPlanInstructions/);
assert.match(prompt, /buildWorkspaceCodeInstructions/);
assert.match(prompt, /WORKSPACE MODE OVERRIDE/);
assert.match(prompt, /input\.task === "workspace-code"/);
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
assert.match(brainRoute, /buildWorkspaceCodeInstructions\(\)/);
assert.match(brainRoute, /workspace-code/);

const orb = readFileSync(new URL("../public/weronika.html", import.meta.url), "utf8");
assert.match(orb, /planningTask = "automation-plan"/);
assert.match(orb, /runAutomationPlan\(prompt, undefined, "workspace-code", workspaceContext\)/);
assert.match(orb, /Open workspace files for context/);
assert.match(orb, /includeHistory: planningTask !== "workspace-code"/);
assert.match(orb, /\/api\/automation\/prepare/);
assert.match(orb, /\/api\/automation\/confirm/);
assert.match(orb, /\/api\/automation\/status/);
assert.match(orb, /function createOrbScene/);
assert.match(orb, /mountDeveloperTools\(\{/);
assert.match(orb, /onPrompt: async/);
assert.match(orb, /openDraftFiles/);
assert.match(orb, /id="blueprintOpenBtn"/);
assert.match(orb, /id="workspaceOpenBtn"/);
assert.match(orb, /\.devtools-launch \{ display: none !important; \}/);
assert.match(orb, /\/api\/blueprint\/capabilities/);
assert.match(orb, /Checking the local 3D model/);
assert.match(orb, /BLUEPRINT · WERONIKA|WERONIKA · BLUEPRINT/);
assert.match(orb, /body\.tech-mode \.hud-controls/);
assert.match(orb, /body\.tech-mode \.hud-left-controls/);
assert.match(orb, /class="tech-return" id="techCloseBtn"/);
assert.match(orb, /addEventListener\("click", returnToOrb\)/);
assert.match(orb, /bloom\.strength = 0\.08/);
assert.match(orb, /bloom\.threshold = 0\.82/);
assert.match(orb, /GENERATE 3D MODEL/);
assert.match(orb, /RELIEF PREVIEW/);
assert.match(orb, /\/api\/blueprint\/reconstruct/);
assert.match(orb, /Your photo is not sent to the cloud/);
assert.match(orb, /id="techDownloadModel"/);
assert.doesNotMatch(orb, /browser-addresses|open-websites|data-tab="browser"/);

const developerTools = readFileSync(
  new URL("../public/developer-tools.js", import.meta.url),
  "utf8",
);
assert.match(developerTools, /WORKSPACE/);
assert.match(developerTools, /workspace-build/);
assert.match(developerTools, /openDraftFiles/);
assert.match(developerTools, /RUN PYTHON/);
assert.match(developerTools, /workspace-explorer/);
assert.match(developerTools, /workspace-editor-pane/);
assert.match(developerTools, /workspace-agent-pane/);
assert.match(developerTools, /downloadWorkspaceZip/);
assert.match(developerTools, /Open-file context is included/);
assert.doesNotMatch(
  developerTools,
  /browser-addresses|open-websites|browser\/open|data-tab="browser"/,
);

const archive = await createStoredZip([{ path: "src/hello.txt", content: "hello" }]);
const zip = new DataView(await archive.arrayBuffer());
assert.equal(zip.getUint32(0, true), 0x04034b50, "ZIP local header signature");
assert.equal(zip.getUint16(6, true), 0x0800, "ZIP names use UTF-8 encoding");
assert.equal(zip.getUint32(14, true), 0x3610a686, "ZIP local header CRC-32");
assert.equal(
  zip.getUint32(archive.size - 22, true),
  0x06054b50,
  "ZIP end-of-central-directory signature",
);
assert.throws(() => createStoredZip([{ path: "../escape.txt", content: "bad" }]), /unsafe path/);

const technical = readFileSync(new URL("../public/technical-viewer.js", import.meta.url), "utf8");
assert.match(technical, /VRMLoaderPlugin/);
assert.match(technical, /@pixiv\/three-vrm@3\.5\.5/);
assert.match(technical, /openVRMFile/);
assert.match(technical, /openGeneratedModelFile/);
assert.match(technical, /openPhotoFile/);
assert.match(technical, /photo-relief/);
assert.match(technical, /active\.vrm\.update\(delta\)/);
assert.match(technical, /hasImageType/);
assert.match(technical, /recognized VRM avatar/);
assert.match(technical, /Check your internet connection/);
assert.match(technical, /DirectionalLight\(0xfff1dc, 0\.9\)/);
assert.match(technical, /AmbientLight\(0x9ecfff, 0\.34\)/);
assert.match(orb, /shallow relief, not full reconstruction/);

console.log("cloud-brain to local-worker planner checks passed");
