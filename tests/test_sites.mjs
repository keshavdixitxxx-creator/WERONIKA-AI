import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const orb = readFileSync(new URL("../public/weronika.html", import.meta.url), "utf8");
const server = readFileSync(
  new URL("../weronika-py/weronika_agent/http_server.py", import.meta.url),
  "utf8",
);
const registry = readFileSync(
  new URL("../weronika-py/weronika_agent/site_registry.py", import.meta.url),
  "utf8",
);

// --- worker routes exist -----------------------------------------------------------
for (const route of [
  "/api/sites/catalog",
  "/api/sites/search",
  "/api/sites/tabs",
  "/api/sites/open",
  "/api/sites/close",
  "/api/sites/focus",
]) {
  assert.ok(server.includes(route), `missing worker route ${route}`);
}

// --- the registry refuses what it should, with a stated reason ---------------------
assert.match(registry, /REFUSED_DOMAINS/);
assert.match(registry, /will not automate/);
for (const blocked of ["vegamovies", "dehashed", "pimeyes", "callbomber", "faceswap"]) {
  assert.ok(registry.includes(blocked), `registry must list ${blocked}`);
}

// --- the orb has a tab panel with close and show ----------------------------------
assert.match(orb, /id="siteTabsList"/);
assert.match(orb, /id="siteTabsStatus"/);
assert.match(orb, /function renderSiteTabs\(tabs\)/);
assert.match(orb, /async function refreshSiteTabs\(\)/);
assert.match(orb, /async function siteTabAction\(path, payload\)/);
assert.match(orb, /\/api\/sites\/focus/);
assert.match(orb, /\/api\/sites\/close/);

// --- the orb's site-open phrase logic is pure, so exercise it directly ------------
function slice(from, to) {
  const start = orb.indexOf(from);
  const end = orb.indexOf(to, start);
  assert.ok(start > 0 && end > start, `could not slice ${from}`);
  return orb.slice(start, end);
}

const siteFns = slice(
  "    // ------------------------------------------------------------------ sites",
  "    function isAutomationRequest(text) {",
);
const api = new Function(`${siteFns}\nreturn { browseSiteNames };`)();

// Plain "open <site>" goes to the registry, never to the cloud planner.
const opened = {
  "open youtube": ["youtube"],
  "open radio garden": ["radio garden"],
  "open gmail, drive, and keep": ["gmail", "drive", "keep"],
  "open google drive and docs": ["google drive", "docs"],
  "open vegamovies": ["vegamovies"],
};
for (const [text, expected] of Object.entries(opened)) {
  assert.deepEqual(api.browseSiteNames(text), expected, text);
}

// Anything that needs the browser planner stays with the planner.
for (const text of [
  "open youtube and play kesariya",
  "open the first result",
  "search for laptops",
  "open github in chrome",
  "send a whatsapp message to boss saying hi",
  "what is the capital of australia",
]) {
  assert.equal(api.browseSiteNames(text), null, text);
}

// --- the wake word launcher is gone ------------------------------------------------
assert.ok(!orb.includes('id="wakeWordBtn"'), "wake word button must be removed");
assert.ok(!orb.includes("toggleWakeWord"), "wake word toggle must be removed");
assert.ok(!orb.includes("updateWakeWordButton"), "wake word painter must be removed");

// --- dead generation routes are gone ----------------------------------------------
assert.ok(!orb.includes("/api/public/image"), "image generation must be removed");
assert.ok(!orb.includes("/api/public/song"), "song generation must be removed");
assert.ok(!orb.includes("/api/public/video"), "video generation must be removed");

console.log("site registry, tab control, and removal checks passed");
