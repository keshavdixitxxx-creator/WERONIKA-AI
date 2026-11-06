import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const orb = readFileSync(new URL("../public/weronika.html", import.meta.url), "utf8");
const planner = readFileSync(new URL("../src/lib/brain-stream.server.ts", import.meta.url), "utf8");
const server = readFileSync(
  new URL("../weronika-py/weronika_agent/http_server.py", import.meta.url),
  "utf8",
);
const tasks = readFileSync(
  new URL("../weronika-py/weronika_agent/tasks.py", import.meta.url),
  "utf8",
);
const web = readFileSync(
  new URL("../weronika-py/weronika_agent/web_adapter.py", import.meta.url),
  "utf8",
);

// --- orb surface ------------------------------------------------------------------
assert.match(orb, /id="browserTaskStatusLine"/);
assert.match(orb, /id="browseCapsLine"/);
assert.match(orb, /id="browserTaskActions"/);
assert.match(orb, /CONFIRM ACTION/);
assert.match(orb, /function isBrowserTaskRequest\(text\)/);
assert.match(orb, /function browsePlanFromPrompt\(text\)/);
assert.match(orb, /async function planAndRunBrowserTask\(text, languageOverride\)/);
assert.match(orb, /async function runBrowserTask\(path, payload\)/);
assert.match(orb, /\/api\/task\/start/);
assert.match(orb, /\/api\/task\/approve/);
assert.match(orb, /\/api\/task\/cancel/);
assert.match(orb, /\/api\/browse\/open/);
assert.match(orb, /\/api\/browse\/capabilities/);
assert.match(orb, /function browseSystemTarget\(text\)/);
assert.match(orb, /if \(isBrowserTaskRequest\(text\)\) return await planAndRunBrowserTask\(text, languageOverride\);/);
assert.match(orb, /pendingBrowserTask/);
// plain "open YouTube, Spotify, GitHub" must keep using the existing tab launcher.
assert.match(orb, /function browseSiteOnly\(text\)/);
assert.match(orb, /if \(browseSiteOnly\(value\)\) return false;/);

// the browser-task block never reaches a bare loopback address
const start = orb.indexOf("// Browser tasks: search, open, read, play");
assert.ok(start > 0, "browser task block exists");
const block = orb.slice(start, orb.indexOf("function isAutomationRequest(text)", start));
assert.ok(block.length > 1000);
assert.doesNotMatch(block, /127\.0\.0\.1|http:\/\/localhost/);

// --- planner ----------------------------------------------------------------------
assert.match(planner, /Use intent "browse"/);
assert.match(planner, /"play_video" \(open YouTube and start the first result/);
assert.match(planner, /"comment" or "reply"/);
assert.match(planner, /Split conjunctions into separate steps/);
assert.match(planner, /Opening a browser application itself \(Edge, Chrome, Firefox\) is not a step/);

// --- worker -----------------------------------------------------------------------
assert.match(server, /"\/api\/task\/start"/);
assert.match(server, /"\/api\/task\/approve"/);
assert.match(server, /"\/api\/browse\/open"/);
assert.match(server, /"\/api\/browse\/capabilities"/);
assert.match(tasks, /MAX_TASK_STEPS = 8/);
assert.match(tasks, /needs_approval/);
assert.match(web, /_BLOCKED_HOSTS/);
assert.match(web, /class BrowserTaskAdapter/);
assert.match(web, /def play\(self, query/);
assert.match(web, /def submit_account_action/);
assert.match(web, /def open_in_system_browser/);

console.log("browser-task orb, planner, and worker checks passed");
