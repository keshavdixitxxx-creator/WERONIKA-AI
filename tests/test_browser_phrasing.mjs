import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

// The orb's phrase→step logic is pure (no DOM), so it can be exercised directly.
const html = readFileSync(new URL("../public/weronika.html", import.meta.url), "utf8");

function slice(from, to) {
  const start = html.indexOf(from);
  const end = html.indexOf(to, start);
  assert.ok(start > 0 && end > start, `could not slice ${from}`);
  return html.slice(start, end);
}

const constants = slice("const BROWSE_SITE_LIST_RE", "function browseSiteOnly(text) {");
const functions = [
  slice("function browseSiteOnly(text) {", "function isBrowserTaskRequest(text) {"),
  slice("function isBrowserTaskRequest(text) {", "async function readWorkerJson"),
  slice("function browsePlanFromPrompt(text) {", "async function runBrowserTask(path, payload) {"),
  slice("const BROWSE_BROWSERS", "async function openInOwnBrowser(target) {"),
].join("\n");

const api = new Function(
  `${constants}\n${functions}\nreturn { browseSiteOnly, isBrowserTaskRequest, browsePlanFromPrompt, browseSystemTarget };`,
)();

// --- a plain list of sites must keep using the existing tab launcher --------------
for (const text of [
  "Open YouTube, Spotify, Wikipedia, and GitHub",
  "open youtube",
  "open gmail and github",
]) {
  assert.equal(api.browseSiteOnly(text), true, text);
  assert.equal(api.isBrowserTaskRequest(text), false, text);
}

// --- everything that needs a browser interaction becomes a task -------------------
for (const text of [
  "search for best laptop under 50000",
  "play kesariya on youtube",
  "open youtube and play kesariya song",
  "comment on this video: great explanation",
  "open the first result and summarize it",
  "open github in chrome",
  "read this page",
]) {
  assert.equal(api.isBrowserTaskRequest(text), true, text);
}

// --- messaging and reply-watch stay with their own handlers -----------------------
for (const text of [
  "send a whatsapp message to boss saying i am on leave",
  "watch my telegram chat with rahul",
]) {
  assert.equal(api.isBrowserTaskRequest(text), false, text);
}

// --- phrase → step mapping -------------------------------------------------------
const cases = [
  ["open youtube and play kesariya song", [{ action: "play_video", target: "kesariya" }]],
  ["play despacito", [{ action: "play_video", target: "despacito" }]],
  ["search for today's weather in ghaziabad", [{ action: "search", target: "today's weather in ghaziabad" }]],
  ["open github", [{ action: "open_url", target: "https://github.com/" }]],
  ["comment: nice explanation", [{ action: "comment", target: "nice explanation" }]],
];
for (const [text, expected] of cases) {
  const plan = api.browsePlanFromPrompt(text);
  assert.ok(plan, `no plan for ${text}`);
  assert.deepEqual(
    plan.steps.map((step) => ({ action: step.action, target: step.target })),
    expected,
    text,
  );
}
assert.equal(api.browsePlanFromPrompt("what is the capital of australia"), null);

// --- "in chrome" is routed to the user's own browser ------------------------------
const chromeGithub = api.browseSystemTarget("open github in chrome");
assert.equal(chromeGithub.browser, "chrome");
assert.ok(chromeGithub.url.startsWith("https://github.com"));
const edgeGithub = api.browseSystemTarget("open edge and go to github.com");
assert.equal(edgeGithub.browser, "edge");
assert.ok(edgeGithub.url.startsWith("https://github.com"));
assert.equal(api.browseSystemTarget("open github in my browser").url, "https://github.com/");
const searched = api.browseSystemTarget("open chrome and search for laptops");
assert.equal(searched.browser, "chrome");
assert.ok(searched.url.startsWith("https://duckduckgo.com/?q="));
assert.equal(api.browseSystemTarget("search for laptops"), null);

console.log("orb browser-task phrasing checks passed");
