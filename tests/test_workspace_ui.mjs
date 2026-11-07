import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const orb = readFileSync(new URL("../public/weronika.html", import.meta.url), "utf8");
const tools = readFileSync(new URL("../public/developer-tools.js", import.meta.url), "utf8");

// --- settings lives in the left control stack, above VOICE CHAT -------------------
const leftStack = orb.slice(
  orb.indexOf('<div class="hud-left-controls"'),
  orb.indexOf('<div class="hud hud-controls">'),
);
const settingsAt = leftStack.indexOf('id="settingsToggleBtn"');
const voiceAt = leftStack.indexOf('id="voiceBtn"');
assert.ok(settingsAt > 0, "settings button must be in the left control stack");
assert.ok(voiceAt > 0, "voice chat button must still exist");
assert.ok(settingsAt < voiceAt, "settings must sit above voice chat");

// It must not be pinned to the top-right any more.
assert.doesNotMatch(orb, /\.settings-toggle-btn\s*\{[^}]*top:\s*20px/s);
assert.doesNotMatch(orb, /\.settings-toggle-btn\s*\{[^}]*right:\s*24px/s);
assert.doesNotMatch(orb, /\.settings-toggle-btn\s*\{[^}]*position:\s*fixed/s);

// Exactly one settings button, and it lives inside the left controls.
assert.equal(orb.split('id="settingsToggleBtn"').length - 1, 1);

// --- blueprint exposes both 3D downloads ------------------------------------------
assert.match(orb, /id="techDownloadModel"[^>]*>DOWNLOAD GLB</);
assert.match(orb, /id="techDownloadVrm"[^>]*>DOWNLOAD VRM</);
assert.match(orb, /\/api\/blueprint\/reconstruct/);
assert.match(orb, /\/api\/blueprint\/vrm/);
// The VRM path must state that the avatar is static.
assert.match(orb, /static avatar, no skeleton/);

// --- workspace is a compact macOS-style shell -------------------------------------
assert.match(tools, /devtools-lights/);
assert.match(tools, /devtools-light\.close/);
assert.match(tools, /devtools-light\.min/);
assert.match(tools, /devtools-light\.max/);
assert.match(tools, /weronika-workspace — WERONIKA AI/);
// Traffic lights actually work.
assert.match(tools, /\$\("\.devtools-light\.close"\)\.addEventListener/);
assert.match(tools, /\$\("\.devtools-light\.min"\)\.addEventListener/);
assert.match(tools, /\$\("\.devtools-light\.max"\)\.addEventListener/);
// Neon-blue palette, tight rows.
assert.match(tools, /background:#061020/);
assert.match(tools, /background:#071625/);
assert.match(tools, /height:36px/);
assert.match(tools, /height:30px/);
assert.match(tools, /font:12px\/1\.4 -apple-system/);

// --- workspace has its own preview pane -------------------------------------------
assert.match(tools, /workspace-preview-pane/);
assert.match(tools, /workspace-preview-frame/);
assert.match(tools, /sandbox="allow-scripts allow-forms allow-modals"/);
assert.match(tools, /function previewBlobUrl\(files\)/);
assert.match(tools, /function loadPreview\(files\)/);
assert.match(tools, /async function refreshPreview\(\)/);
// Preview state is declared before use (no temporal dead zone).
const declareAt = tools.indexOf("let previewFiles = [];");
const useAt = tools.indexOf("merged !== previewFiles");
assert.ok(declareAt > 0 && useAt > declareAt, "preview state must be declared before use");

// --- workspace replies stay inside the workspace pane ------------------------------
assert.doesNotMatch(
  orb,
  /onPrompt: async[\s\S]{0,320}appendChat\("assistant"/,
  "workspace replies must not be echoed into the main chat",
);
assert.match(tools, /appendWorkspaceMessage\("user", prompt\)/);

console.log("settings placement, blueprint VRM, and workspace UI checks passed");
