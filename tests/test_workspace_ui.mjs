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

// --- workspace is a VS Code layout with macOS traffic lights -----------------------
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
// The VS Code parts: activity bar, side bar with Explorer and Search, editor tabs,
// breadcrumbs, output panel, status bar, command centre, and menus.
for (const part of [
  "workspace-activity",
  "workspace-explorer",
  "workspace-open-editors",
  "workspace-search-input",
  "devtools-editor-tabs",
  "devtools-crumbs",
  "workspace-panel",
  "workspace-statusbar",
  "devtools-command",
  "devtools-menubar",
  "devtools-quickopen",
]) {
  assert.match(tools, new RegExp(`class="(?:[^"]* )?${part}[ "]`), `the Workspace has a ${part}`);
}
assert.match(tools, />SAVE ALL</);
assert.match(tools, /async function saveAll\(\)/);
// The editor is a text area over a syntax-coloured copy of its text. Both layers share
// one rule for their metrics, and nothing in the coloured layer may change a glyph's
// width, or the text would drift away from the caret.
assert.match(tools, /import \{[^}]*highlightCode[^}]*\} from "\.\/workspace-syntax\.js";/);
assert.match(tools, /\.devtools-highlight, \.devtools-editor \{[^}]*font:12\.5px\/19px var\(--mono\)/);
const tokenRules = tools.match(/\.tk-[a-z] \{[^}]*\}/g) || [];
assert.ok(tokenRules.length >= 14, "every token class has a colour");
for (const rule of tokenRules) {
  assert.doesNotMatch(rule, /font-weight|font-style|font-size|letter-spacing/, rule);
}
// The focused editor shows a caret and a current-line bar, not a frame around the code.
assert.match(tools, /\.devtools-panel \.devtools-editor:focus-visible \{ outline:0; \}/);
// The orb puts its theme colour on <body> as a filter. The Workspace is mounted beside
// <body> so that it stays neon blue, and only follows the brightness setting.
assert.match(tools, /document\.documentElement\.append\(panel\)/);
assert.doesNotMatch(tools, /document\.body\.append\(panel\)/);
assert.match(tools, /html\[data-weronika-dim\] \.devtools-panel \{ filter:brightness\(var\(--weronika-brightness,1\)\); \}/);
assert.match(orb, /setProperty\("--weronika-brightness", String\(brightness \/ 100\)\)/);
assert.match(orb, /toggleAttribute\("data-weronika-dim", brightness !== 100\)/);
// Keys typed in the Workspace must not reach the orb's single-key shortcuts.
assert.match(
  tools,
  /panel\.addEventListener\("keydown", \(event\) => \{\s*handleShortcut\(event\);\s*event\.stopPropagation\(\);/,
);
// File names and file contents come from disk and from the brain: they are only ever
// written as text. The single innerHTML sink besides the static panel markup is the
// coloured layer, which takes the escaped output of the syntax module.
const htmlSinks = tools.match(/\.innerHTML\s*=[^;]*;/g) || [];
assert.equal(htmlSinks.length, 2, "exactly two innerHTML assignments");
assert.ok(htmlSinks.some((sink) => sink.startsWith(".innerHTML = `")), "the static panel markup");
assert.ok(
  htmlSinks.includes('.innerHTML = plain ? "" : highlightCode(text, language.id);'),
  "the coloured layer",
);
assert.doesNotMatch(tools, /insertAdjacentHTML|outerHTML|document\.write/);

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

// --- a Workspace statement goes to the orb, the orb asks the brain ------------------
assert.match(tools, /appendWorkspaceMessage\("user", prompt\)/);
assert.match(tools, /await onPrompt\(prompt, getWorkspaceContext\(\), \{ onStage: setStage \}\)/);
assert.match(
  orb,
  /onPrompt: async \(prompt, workspaceContext, relay\) =>\s*relayWorkspaceStatement\(prompt, workspaceContext, relay\)/,
);
const relayAt = orb.indexOf("    async function relayWorkspaceStatement(");
const relay = orb.slice(relayAt, orb.indexOf("    async function sendChatMessage(", relayAt));
assert.ok(relayAt > 0 && relay.length > 400, "the orb has a Workspace relay");
// The orb shows the statement in its own chat, asks the brain with the open files,
// shows the answer, and remembers the exchange as a Workspace turn.
const relaySteps = [
  'beginTurn("workspace")',
  'stage("orb")',
  'appendChat("user", prompt, { via: "Workspace" })',
  'stage("brain")',
  'runAutomationPlan(prompt, undefined, "workspace-code", workspaceContext)',
  'appendChat("assistant", answer, { banner: false })',
  "rememberTurn(turn, prompt, answer)",
  'stage(turn.files ? "workspace" : "answer")',
];
let relayCursor = -1;
for (const step of relaySteps) {
  const at = relay.indexOf(step, relayCursor + 1);
  assert.ok(at > relayCursor, `the relay does, in order: ${step}`);
  relayCursor = at;
}
// The files the brain returns are delivered into the Workspace editor as drafts.
assert.match(orb, /const opened = await developerTools\.openDraftFiles\(files\);/);
assert.match(orb, /if \(currentTurn\) currentTurn\.files = files\.map\(\(file\) => file\.path\);/);
assert.match(tools, /origin: "weronika"/);
// A file the brain returns unchanged is not presented as a change, and the orb says so.
assert.match(tools, /async function storedContent\(path\)/);
assert.match(tools, /return \{ drafts, unchanged \};/);
assert.match(orb, /Array\.isArray\(opened\.unchanged\) \? opened\.unchanged : \[\]/);
assert.match(orb, /Unchanged, already stored: /);
// Weronika's newer draft replaces her older one. Only text the user typed and has not
// saved is protected by a question, asked once for all files.
assert.match(tools, /state\.touched = true;/);
assert.match(tools, /current\.touched === true &&/);
assert.equal(
  (tools.match(/would replace your own unsaved edits in:/g) || []).length,
  1,
  "one question covers every file",
);
// SAVE ALL asks once before replacing stored files with drafts.
const saveAllAt = tools.indexOf("async function saveAll()");
const saveAllBody = tools.slice(
  saveAllAt,
  tools.indexOf("async function collectWorkspaceFiles()", saveAllAt),
);
assert.ok(saveAllAt > 0 && saveAllBody.length > 300, "SAVE ALL exists");
assert.equal((saveAllBody.match(/window\.confirm\(/g) || []).length, 1, "SAVE ALL asks once");
assert.match(saveAllBody, /saveFile\(path, \{ batch: true, overwrite: true \}\)/);
// Folded to its title bar, the Workspace unfolds before it shows a menu or the file finder.
assert.match(tools, /function openQuick\(config\) \{\s*unfold\(\);/);
assert.match(tools, /function openMenu\(button\) \{\s*unfold\(\);/);
// On a narrow screen the Explorer lies over the editor, so it folds away by itself.
assert.match(tools, /window\.matchMedia\("\(max-width: 820px\)"\)/);
// The preview keeps a module a module, and inlined code cannot end its own tag early.
assert.ok(tools.includes('js.replace(/<\\/script/gi, "<\\\\/script")'), "inlined scripts are closed safely");
assert.ok(tools.includes('css.replace(/<\\/style/gi, "<\\\\/style")'), "inlined styles are closed safely");
assert.match(tools, /\/\\btype=\["'\]module\["'\]\/i\.test\(match\) \? ' type="module"' : ""/);
// The Workspace reports whether it covers the orb, and shows the remembered conversation.
assert.match(tools, /document\.body\.classList\.toggle\(\s*"workspace-open"/);
assert.match(orb, /document\.body\.classList\.contains\("workspace-open"\)/);
assert.match(tools, /function showConversation\(turns\)/);
assert.match(tools, /turn\.src === "workspace"/);
assert.ok(
  orb.split("developerTools.showConversation(").length - 1 >= 4,
  "the orb restores and clears the Workspace conversation with its memory",
);
// Unsaved drafts are kept in this browser, so a restart does not lose them.
assert.match(tools, /const SESSION_KEY = "weronika\.workspace\.session\.v1";/);
assert.match(tools, /function restoreSession\(\)/);

console.log("settings placement, blueprint VRM, and workspace UI checks passed");
