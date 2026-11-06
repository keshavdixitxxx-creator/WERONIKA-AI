import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const orb = readFileSync(new URL("../public/weronika.html", import.meta.url), "utf8");
const planner = readFileSync(new URL("../src/lib/brain-stream.server.ts", import.meta.url), "utf8");
const server = readFileSync(
  new URL("../weronika-py/weronika_agent/http_server.py", import.meta.url),
  "utf8",
);

// --- orb surface -----------------------------------------------------------------
assert.match(orb, /id="watchOpenBtn"/);
assert.match(orb, /◎ REPLY WATCH/);
assert.match(orb, /id="skillsOpenBtn"/);

// Both launchers belong to Settings, never to the main-screen launcher row.
const settingsPanelStart = orb.indexOf('<div class="settings-panel" id="settingsPanel">');
const settingsPanelMarkup = orb.slice(
  settingsPanelStart,
  orb.indexOf("<style>", settingsPanelStart),
);
assert.ok(
  settingsPanelMarkup.includes('id="watchOpenBtn"'),
  "reply watch button must live in Settings",
);
assert.ok(
  settingsPanelMarkup.includes('id="skillsOpenBtn"'),
  "skills button must live in Settings",
);
const launcherRow = orb.slice(
  orb.indexOf('<div class="orb-feature-launchers"'),
  orb.indexOf('<section class="chat-panel"'),
);
assert.ok(
  !launcherRow.includes('id="watchOpenBtn"'),
  "reply watch button must not sit on the main screen",
);
assert.ok(
  !launcherRow.includes('id="skillsOpenBtn"'),
  "skills button must not sit on the main screen",
);
assert.match(launcherRow, /id="blueprintOpenBtn"/);
assert.match(launcherRow, /id="workspaceOpenBtn"/);
assert.match(orb, /id="watchPanel"/);
assert.match(orb, /id="skillsPanel"/);
assert.match(orb, /id="watchPlatform"/);
assert.match(orb, /id="watchMode"/);
assert.match(orb, /id="watchRule"/);
assert.match(orb, /id="watchItems"/);

// --- orb behaviour ---------------------------------------------------------------
assert.match(orb, /function hasWatchIntent\(text\)/);
assert.match(orb, /async function continueReplyWatch\(text\)/);
assert.match(orb, /async function runReplyWatchPlan\(text, languageOverride\)/);
assert.match(orb, /async function scanReplyWatch\(manual = false\)/);
assert.match(orb, /\/api\/watch\/add/);
assert.match(orb, /\/api\/watch\/scan/);
assert.match(orb, /\/api\/watch\/reply/);
assert.match(orb, /\/api\/watch\/confirm/);
assert.match(orb, /\/api\/watch\/leave/);
assert.match(orb, /\/api\/skills/);
assert.match(
  orb,
  /if \(hasWatchIntent\(text\)\) return await runReplyWatchPlan\(text, languageOverride\);/,
);
assert.match(orb, /if \(hasWatchIntent\(value\)\) return true;/);
assert.match(orb, /watchSuspectUnsupportedPlan/);
assert.match(orb, /document\.hidden \|\| !localAutomationConnected/);
assert.match(orb, /say “leave it”/i);

// --- the client never talks to a bare loopback address ---------------------------
const watchStart = orb.indexOf("// Reply watch: watch named chats");
assert.ok(watchStart > 0, "reply-watch block exists");
const watchBlock = orb.slice(watchStart, orb.indexOf("async function loadSkills()", watchStart));
assert.doesNotMatch(watchBlock, /127\.0\.0\.1|http:\/\/localhost/);

// --- planner language -------------------------------------------------------------
assert.match(planner, /reply-watch request/);
assert.match(planner, /never as "open_sites" merely because a chat, group, or person name/);
assert.match(planner, /never promise that Weronika will answer without the user/);

// --- worker routes ----------------------------------------------------------------
assert.match(server, /"\/api\/watch\/add"/);
assert.match(server, /"\/api\/watch\/scan"/);
assert.match(server, /"\/api\/watch\/confirm"/);
assert.match(server, /"\/api\/watch\/leave"/);
assert.match(server, /"\/api\/skills"/);

console.log("reply-watch orb, planner, and worker route checks passed");
