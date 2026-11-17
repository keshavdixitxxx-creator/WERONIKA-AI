// Handling an incoming call: the orb's CALL WATCH panel, its offline reader for call
// sentences, and the worker routes behind both. The rule these checks exist to protect is
// the one in weronika-py/README.md — Weronika asks about EVERY call before she answers it,
// and tells the caller she is an AI. Nothing here may imply an "always answer" switch.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import {
  callChannelWord,
  callRouteWord,
  callWorkerOfflineReply,
  hasCallAnswer,
  hasCallIntent,
  parseCallDecision,
  parseCallRequest,
} from "../public/weronika-instant.js";

const orb = readFileSync(new URL("../public/weronika.html", import.meta.url), "utf8");
const server = readFileSync(
  new URL("../weronika-py/weronika_agent/http_server.py", import.meta.url),
  "utf8",
);
const calls = readFileSync(
  new URL("../weronika-py/weronika_agent/calls.py", import.meta.url),
  "utf8",
);
const skills = readFileSync(
  new URL("../weronika-py/weronika_agent/watch_skills.py", import.meta.url),
  "utf8",
);

// --- orb surface -------------------------------------------------------------------
assert.match(orb, /id="callOpenBtn"/);
assert.match(orb, /☎ CALL WATCH/);
assert.match(orb, /id="callPanel"/);
assert.match(orb, /WERONIKA · CALL WATCH/);

// The launcher belongs to Settings, next to REPLY WATCH — never to the main launcher row.
const settingsStart = orb.indexOf('<div class="settings-panel" id="settingsPanel">');
assert.ok(settingsStart > 0, "settings panel exists");
const settingsMarkup = orb.slice(settingsStart, orb.indexOf("<style>", settingsStart));
assert.ok(settingsMarkup.includes('id="callOpenBtn"'), "call watch button must live in Settings");
const launcherRow = orb.slice(0, settingsStart);
assert.ok(
  !launcherRow.includes('id="callOpenBtn"'),
  "call watch must not be added to the main-screen launcher row",
);

// The old blanket refusal is gone: the orb no longer claims calls are unsupported.
assert.doesNotMatch(
  orb,
  /Incoming-call detection, answering, live call audio, and call summaries are not supported yet\./,
);
assert.match(orb, /CALL WATCH asks you about each incoming call/);

// --- the ask-first rule, in the panel's own words ----------------------------------
const panelStart = orb.indexOf('<div class="watch-panel call-panel" id="callPanel"');
assert.ok(panelStart > 0, "call panel exists");
const panelEnd = orb.indexOf('<div class="settings-panel" id="settingsPanel">', panelStart);
assert.ok(panelEnd > panelStart, "the call panel closes before the settings panel opens");
const panel = orb.slice(panelStart, panelEnd);
// The panel's copy is wrapped across lines in the HTML; phrases are checked on one line.
const panelText = panel.replace(/\s+/g, " ");
assert.match(panelText, /Are you able to handle the call, or should I take it\?/);
assert.match(panelText, /about <strong>every<\/strong> one/);
assert.match(panelText, /A remembered preference is never used: each call is asked separately\./);
assert.match(panelText, /tells\s+the caller she is your AI assistant/);
assert.match(panelText, /WERONIKA TAKES IT/);
assert.match(panelText, /I'LL TAKE IT/);
// All three answers exist as buttons — in the panel and in the chat — and each one maps to
// the worker's own decision word, so a click cannot mean something else.
for (const [label, decision] of [
  ["WERONIKA TAKES IT", "weronika"],
  ["I'LL TAKE IT", "user"],
  ["IGNORE IT", "ignore"],
]) {
  assert.ok(
    orb.includes(`{ label: "${label}", decision: "${decision}" }`),
    `panel button ${label} maps to ${decision}`,
  );
  assert.ok(orb.includes(`label: "${label}"`), `chat offers ${label}`);
}
// The card is built for every ringing call, with her question on it.
assert.match(orb, /item\.question \|\| "Are you able to handle the call, or should I take it\?"/);
assert.match(panelText, /She does not dial out/);
assert.match(panelText, /never repeats a one-time code, password, card number or UPI handle/);
assert.match(panelText, /never written to disk/);
// Typed mode is a real mode, not a hidden failure: the panel says how to drive it.
assert.match(panel, /SHE HEARS THIS/);
assert.match(panel, /WERONIKA SAYS THIS/);
// Typed mode names the installer that ends it (the hint is rendered, not static markup).
assert.match(panelText, /id="callTypedHint"/);
assert.match(orb, /Typed mode: run setup-calls\.bat for hearing and speaking/);
// There is no "always answer" control anywhere in the panel.
assert.doesNotMatch(panelText, /auto[_ ]?answer|always answer|answer all calls/i);

// --- endpoints the panel talks to ---------------------------------------------------
for (const path of [
  "/api/call/status",
  "/api/call/capabilities",
  "/api/call/scan",
  "/api/call/decide",
  "/api/call/hear",
  "/api/call/say",
  "/api/call/handover",
  "/api/call/end",
  "/api/call/summary",
  "/api/call/configure",
  "/api/call/simulate",
]) {
  assert.ok(orb.includes(`"${path}"`), `orb calls ${path}`);
  assert.ok(server.includes(`"${path}"`), `worker serves ${path}`);
}
// The client never talks to a bare loopback address: it is served by the same worker.
const callBlockStart = orb.indexOf("// ---- Call watch ---");
assert.ok(callBlockStart > 0, "call-watch block exists");
const callBlockEnd = orb.indexOf("// Alarms, timers and reminders:", callBlockStart);
assert.ok(callBlockEnd > callBlockStart, "the call-watch block has a clear end");
const callBlock = orb.slice(callBlockStart, callBlockEnd);
assert.doesNotMatch(callBlock, /127\.0\.0\.1|http:\/\/localhost/);

// --- polling: a call rings for seconds, so the scan is not paused in the background ---
assert.match(orb, /function startCallWatchPolling\(\)/);
assert.match(orb, /startCallWatchPolling\(\);/);
assert.match(orb, /const CALL_SCAN_MS = 3000;/);
const ticker = orb.slice(
  orb.indexOf("function startCallWatchPolling()"),
  orb.indexOf("if (callOpenBtn) callOpenBtn.addEventListener"),
);
assert.doesNotMatch(ticker, /document\.hidden/, "call scanning must continue while the tab is hidden");
// Asking out loud and notifying away are both wired, so the question reaches you.
assert.match(orb, /speak\(question\);/);
assert.match(orb, /notifyAway\(`Incoming call from/);

// --- routing in the chat pipeline ---------------------------------------------------
assert.match(orb, /const called = await runCallPlan\(text\);/);
assert.match(orb, /async function runCallPlan\(text\)/);
assert.match(orb, /if \(hasCallIntent\(value\) \|\| callNeedsAnAnswer\(value\)\) return true;/);
// Calls are routed before reply watch: while one is ringing, "you handle it" is an answer
// to Weronika's question and must not be planned as a message.
assert.ok(
  orb.indexOf("await runCallPlan(text)") < orb.indexOf("if (hasWatchIntent(text)) {"),
  "call routing happens before reply-watch routing",
);
// And before the instant commands: "answer the call" or "kaat do" must reach the ringing
// call, not the offline "I can't answer calls" refusal that the instant parser still keeps
// for a browser with no worker attached.
assert.ok(
  orb.indexOf("await runCallPlan(text)") <
    orb.indexOf("const instant = parseInstantCommand(text, new Date());"),
  "call routing happens before instant-command routing",
);
// A call request is answered on this computer, or honestly not at all.
assert.match(orb, /callWorkerOfflineReply\(value\)/);
assert.match(orb, /postLocalJson\("\/api\/message", \{ text: value \}\)/);

// --- worker routes -------------------------------------------------------------------
assert.match(server, /has_call_intent\(text\) or \(calls is not None and calls\.current\(\) is not None\)/);
assert.ok(
  server.indexOf("has_call_intent(text)") < server.indexOf("has_watch_intent(text)"),
  "the worker checks call intents before watch intents",
);
assert.match(server, /CallWatchError/);
assert.match(server, /"call_watch": calls is not None/);
assert.match(server, /def _call_stream\(self, path: str, data: dict\[str, object\], progress\)/);
assert.match(server, /def _call_route\(self, data: dict\[str, object\]\)/);
assert.match(server, /"\/api\/call\/status"/);
assert.match(server, /"\/api\/call\/capabilities"/);
assert.match(server, /"\/api\/call\/links"/);
// An example is chosen by channel, never by handing the channel word to the scenario lookup.
assert.match(server, /_scenario_for\(text, intent\.channel\)/);

// Python splits long sentences across lines by implicit concatenation; join them so a
// promise can be asserted as the sentence a person would read.
const callsFlat = calls.replace(/"\s*\n\s*"/g, "");

// --- the service keeps the two promises ----------------------------------------------
assert.match(calls, /"asks_every_call": True/);
assert.match(calls, /"discloses_every_call": True/);
assert.match(calls, /auto_answer", "always_answer", "answer_all"/);
assert.match(callsFlat, /She asks about each call, because only you know whether you can take it\./);
assert.match(callsFlat, /Weronika cannot be set to answer calls automatically\./);
// The question travels with the item, so a polling orb can ask it.
assert.match(calls, /payload\["question"\] = self\.prompt\(item\)/);

// --- the skills catalog no longer refuses calls wholesale ------------------------------
assert.match(skills, /id="call-watch-ask"/);
assert.match(skills, /id="call-handle"/);
assert.match(skills, /id="call-setup"/);
assert.match(skills, /id="call-example"/);
assert.doesNotMatch(skills, /"id": "calls",/);
assert.match(skills, /"id": "telegram-calls"/);
assert.match(skills, /"id": "outgoing-calls"/);
assert.match(skills, /"id": "iphone-sim-calls"/);

// --- the offline reader: what belongs to the call worker -------------------------------
for (const text of [
  "handle my calls",
  "Can you handle my calls?",
  "meri calls uthao",
  "stop handling my calls",
  "don't answer my calls",
  "scan calls",
  "is anyone calling?",
  "call status",
  "which phone is connected",
  "show me an example call",
  "show me an example of a whatsapp call",
  "end the call",
  "give me the call",
  "say: I will call you back in ten minutes",
  "send the call summary to Boss on whatsapp",
]) {
  assert.ok(hasCallIntent(text), `recognised as a call request: ${text}`);
}

for (const text of [
  "call me a cab",
  "call me an uber",
  "I'll call you back tomorrow",
  "I will call him later",
  "what do you call this?",
  "we call it the blue box",
  "lets play Call of Duty",
  "that was a wake-up call",
  "phone a friend",
  "how are you",
  "open WhatsApp",
  "watch my WhatsApp chat with Boss",
  "play Kesariya on Spotify",
  "give me an example of a python function",
  "",
]) {
  assert.ok(!hasCallIntent(text), `left alone as ordinary conversation: ${text}`);
}

// --- the offline reader: what each sentence means --------------------------------------
const actions = {
  "handle my calls": "enable",
  "meri calls uthao": "enable",
  "handle calls on whatsapp": "enable",
  "stop handling my calls": "disable",
  "don't answer my calls": "disable",
  "turn off call handling": "disable",
  "scan calls": "scan",
  "who is calling?": "scan",
  "call status": "status",
  "show me the call summary": "status",
  "which phone is connected": "links",
  "what audio route for calls": "links",
  "show me an example call": "simulate",
  "simulate a whatsapp call": "simulate",
  "you handle it": "decide",
  "I'll take it": "decide",
  "ignore it": "decide",
  "give me the call": "handover",
  "hand it over": "handover",
  "end the call": "end",
  "kaat do": "end",
  "he said the papers are ready": "hear",
  "usne kaha shaam ko aayega": "hear",
  "say: I will call you back": "dictate",
  "send the call summary to Rahul on telegram": "summary_send",
  "read it out anyway": "read_secret",
  "call me a cab": "unhandled",
  "what do you call this?": "unhandled",
  "": "unhandled",
};
for (const [text, want] of Object.entries(actions)) {
  assert.equal(parseCallRequest(text).action, want, `action for “${text}”`);
}

// The most dangerous misreading in the whole grammar: a refusal must never enable answering.
assert.equal(parseCallRequest("don't answer my calls").action, "disable");
assert.notEqual(parseCallRequest("don't answer my calls").action, "enable");

// Channels and routes are named in plain words.
assert.equal(callChannelWord("handle calls on whatsapp"), "whatsapp");
assert.equal(callChannelWord("handle my phone calls"), "sim");
assert.equal(callChannelWord("on telegram"), "telegram");
assert.equal(callChannelWord("nothing relevant"), "");
assert.equal(callRouteWord("use bluetooth"), "bluetooth");
assert.equal(callRouteWord("through line-in"), "aux");
assert.equal(callRouteWord("on speaker"), "speaker_mic");
assert.equal(callRouteWord("nothing relevant"), "");

// --- the three answers to her question --------------------------------------------------
const decisions = {
  "you handle it": "weronika",
  "handle it": "weronika",
  "answer it": "weronika",
  "take the call": "weronika",
  "tum utha lo": "weronika",
  "Weronika, you take it": "weronika",
  "yes please": "weronika",
  "I'll take it": "user",
  "i will handle it": "user",
  "let me take it": "user",
  "main uthaunga": "user",
  "leave it to me": "user",
  // A refusal plus a claim is a claim: you take it, the call is not ignored.
  "don't answer, I'll take it": "user",
  "ignore it": "ignore",
  "let it ring": "ignore",
  "decline it": "ignore",
  "mat uthao": "ignore",
  "nahi uthao": "ignore",
  "no": "ignore",
};
for (const [text, want] of Object.entries(decisions)) {
  assert.equal(parseCallDecision(text), want, `decision for “${text}”`);
}
for (const text of ["how are you", "what is the weather", "tell me a joke", ""]) {
  assert.equal(parseCallDecision(text), "", `not an answer: “${text}”`);
}

// A short answer carries no call word at all — "you handle it", "kaat do" — so it is not a
// call request on its own. It is recognised as an answer, and the orb only forwards it while
// a call is ringing or live, which is when the worker is waiting for exactly that.
for (const text of ["you handle it", "kaat do", "hand it over", "ignore it", "I'll take it"]) {
  assert.ok(!hasCallIntent(text), `a bare answer is not a call request on its own: ${text}`);
  assert.ok(hasCallAnswer(text), `a bare answer is recognised while a call is live: ${text}`);
}

// A short answer is only forwarded while a call is actually ringing or live.
assert.ok(hasCallAnswer("you handle it"));
assert.ok(hasCallAnswer("kaat do"));
assert.ok(hasCallAnswer("hand it over"));
assert.ok(!hasCallAnswer("how are you"));
assert.ok(!hasCallAnswer("send a WhatsApp message to Boss"));
assert.ok(!hasCallAnswer(""));

// --- offline honesty --------------------------------------------------------------------
for (const text of ["handle my calls", "scan calls", "you handle it"]) {
  const reply = callWorkerOfflineReply(text);
  assert.match(reply, /local worker is offline/);
  assert.match(reply, /start\.bat/i);
  assert.match(reply, /No call was answered, ended or dialled\.|Nothing was dialled\./);
  assert.doesNotMatch(reply, /I have (?:answered|handled) the call/i);
}
assert.match(callWorkerOfflineReply("handle calls on telegram"), /Telegram has no calling/);
assert.match(callWorkerOfflineReply("scan calls"), /cannot look for a ringing call/);
assert.match(callWorkerOfflineReply("show me an example call"), /cannot run an example call/);
// Even offline, a sentence that is not a call request gets no call answer at all.
assert.match(callWorkerOfflineReply("how are you"), /no call can be watched/);

console.log("call-watch orb, offline reader, and worker route checks passed");
