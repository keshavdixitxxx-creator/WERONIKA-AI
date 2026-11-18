import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const orb = readFileSync(new URL("../public/weronika.html", import.meta.url), "utf8");

// --- the self-voice filter, lifted out of the orb and run for real -------------------
// The microphone stays open while she speaks, so her own voice comes back through the
// recognizer. These are the functions that decide what is echo and what is the user.
const start = orb.indexOf("// --- her own voice, remembered so she does not answer herself");
const end = orb.indexOf("function queueSpeech(text, { append = false } = {}) {");
assert.ok(start > 0 && end > start, "the echo-filter block must sit just before queueSpeech");
const filterSource = orb.slice(start, end);

const harness = new Function(
  `
  const LIVE_ECHO_TAIL_MS = 420;
  const LIVE_ECHO_WINDOW_MS = 9000;
  const LIVE_ECHO_MATCH_MS = 2600;
  const LIVE_ECHO_RATIO = 0.72;
  let liveEchoUntil = 0;
  let liveSpoken = [];
  let liveSpeakingNow = "";
  let liveLastSpoken = "";
  let speechSynthesisAvailable = false;
  const logs = [];
  function logVoice(text) { logs.push(text); }
  ${filterSource}
  return {
    heardOwnVoice,
    noteSpokenForEcho,
    sheIsSpeaking,
    normalizeHeard,
    logs,
    set speaking(value) { liveEchoUntil = value ? Date.now() + 5000 : 0; },
    set nowSpeaking(text) { liveSpeakingNow = normalizeHeard(text); },
    set lastSpoken(text) { liveLastSpoken = normalizeHeard(text); },
    reset() { liveSpoken = []; liveSpeakingNow = ""; liveLastSpoken = ""; liveEchoUntil = 0; },
  };
`,
)();

// Nothing is echo while she is quiet: your speech must always get through.
harness.reset();
harness.speaking = false;
harness.nowSpeaking = "I will tell Commander about this conversation.";
assert.equal(harness.heardOwnVoice("I will tell Commander about this conversation."), false);
assert.equal(harness.heardOwnVoice("what is the time"), false);

// Her own sentence, heard back verbatim through the speakers, is echo.
harness.speaking = true;
assert.equal(harness.heardOwnVoice("I will tell Commander about this conversation."), true);
// So is a fragment of it, which is what a recognizer usually catches.
assert.equal(harness.heardOwnVoice("tell Commander about this"), true);
assert.equal(harness.heardOwnVoice("I will tell Commander"), true);

// But you talking over her is not echo, and must be allowed to interrupt.
assert.equal(harness.heardOwnVoice("stop, call Rahul instead"), false);
assert.equal(harness.heardOwnVoice("what is the weather today"), false);
assert.equal(harness.heardOwnVoice("no no, hang up now"), false);

// A short phrase only counts as echo when every word of it is one of hers, so "yes"
// and "wait" survive even mid-sentence.
harness.nowSpeaking = "Should I ask Commander to call you back?";
assert.equal(harness.heardOwnVoice("call you back"), true);
assert.equal(harness.heardOwnVoice("wait"), false);
assert.equal(harness.heardOwnVoice("yes"), false);
assert.equal(harness.heardOwnVoice("hold on"), false);

// The sentence she just finished still echoes in the room, so it is filtered too.
harness.nowSpeaking = "Thank you for calling.";
harness.lastSpoken = "I have written that down and I will pass it on.";
assert.equal(harness.heardOwnVoice("I have written that down"), true);

// Hindi and Hinglish normalise the same way, so echo is caught in either script.
harness.reset();
harness.speaking = true;
harness.nowSpeaking = "Main aapki AI assistant hoon, Commander abhi phone par nahi aa sakte.";
assert.equal(harness.heardOwnVoice("main aapki AI assistant hoon"), true);
assert.equal(harness.heardOwnVoice("Commander abhi phone par nahi aa sakte"), true);
assert.equal(harness.heardOwnVoice("tum kaun ho"), false);
harness.nowSpeaking = "मैं वेरोनिका हूँ, कमांडर की एआई असिस्टेंट।";
assert.equal(harness.heardOwnVoice("मैं वेरोनिका हूँ"), true);
assert.equal(harness.heardOwnVoice("कितने बजे हैं"), false);

// Punctuation, case and quote marks must not change the verdict.
harness.nowSpeaking = "Hello, you have reached Commander's phone!";
assert.equal(harness.heardOwnVoice("hello you have reached commanders phone"), true);
assert.equal(harness.heardOwnVoice("HELLO YOU HAVE REACHED COMMANDER'S PHONE"), true);

// Long speech is judged by overlap, not by exact containment.
harness.nowSpeaking =
  "I am an AI and I cannot hand this phone over while Commander is away so I will tell him that you called";
assert.equal(harness.heardOwnVoice("I am an AI and I cannot hand this phone over while Commander is away"), true);
assert.equal(harness.heardOwnVoice("I am an AI and I cannot hand this phone over but please book a cab"), false);

// Empty and noise-only transcripts are never treated as your turn.
assert.equal(harness.heardOwnVoice(""), false);
assert.equal(harness.heardOwnVoice("   "), false);

// --- turn endpointing, lifted out and run for real ----------------------------------
// This is the "no lag" half: a pause commits the turn instead of waiting for the
// browser's own slow end-of-speech decision, repeats are dropped, and her own voice
// never becomes a turn even if it reaches the commit.
const liveStart = orb.indexOf("// --- live voice: one continuous conversation");
const liveEnd = orb.indexOf("async function startVoiceRecognition(opts = {}) {");
assert.ok(liveStart > 0 && liveEnd > liveStart, "the live-voice helpers must sit before startVoiceRecognition");
const liveSource = orb.slice(liveStart, liveEnd);

const turn = new Function(
  `
  const LIVE_SILENCE_MS = 60;   // shortened so the test does not wait on real speech
  const LIVE_ECHO_TAIL_MS = 420;
  const LIVE_ECHO_WINDOW_MS = 9000;
  const LIVE_ECHO_MATCH_MS = 2600;
  const LIVE_ECHO_RATIO = 0.72;
  const LIVE_BARGE_IN_MS = 180;
  let liveEchoUntil = 0, liveSpoken = [], liveSpeakingNow = "", liveLastSpoken = "";
  let livePending = "", liveInterim = "", livePendingAt = 0;
  let liveCommitTimer = null, liveLastCommitted = "", liveLastCommittedAt = 0;
  let liveBargeInSince = 0, liveBargedIn = false, liveEchoLoggedAt = 0;
  let speechSynthesisAvailable = false;
  let spokenLang = "en-IN";
  const logs = [], sent = [], shown = [];
  const chatInput = { value: "", dispatchEvent() {} };
  function logVoice(text) { logs.push(text); }
  function detectSpokenLanguage() { return "en"; }
  function speechTagForLanguage() { return "en-IN"; }
  function setSpokenLang() {}
  function speechLanguageName() { return "English"; }
  async function sendChatMessage(options) { sent.push(options); }
  function appendChat(who, text) { shown.push([who, text]); }
  async function parseVoiceCommand(text) { return "answered: " + text; }
  function speak(text) { shown.push(["spoken", text]); }
  ${filterSource}
  ${liveSource}
  return {
    scheduleLiveCommit,
    resetLiveTurn,
    logs, sent, shown,
    set pending(value) { livePending = value; },
    set interim(value) { liveInterim = value; },
    set speaking(value) { liveEchoUntil = value ? Date.now() + 5000 : 0; },
    set nowSpeaking(text) { liveSpeakingNow = normalizeHeard(text); },
  };
`,
)();

const settle = () => new Promise((resolve) => setTimeout(resolve, 160));

// A pause commits what was heard.
turn.pending = "what is the time";
turn.scheduleLiveCommit();
await settle();
assert.equal(turn.sent.length, 1, "one turn should have been sent");
assert.equal(turn.sent[0].text, "what is the time");
assert.equal(turn.sent[0].source, "voice");

// The recognizer repeating itself is not a second turn.
turn.pending = "what is the time";
turn.scheduleLiveCommit();
await settle();
assert.equal(turn.sent.length, 1, "an immediate repeat must not be sent twice");

// Her own voice reaching the commit is dropped, not answered.
turn.speaking = true;
turn.nowSpeaking = "I am Weronika, Commander's AI assistant.";
turn.pending = "I am Weronika, Commander's AI assistant.";
turn.scheduleLiveCommit();
await settle();
assert.equal(turn.sent.length, 1, "her own voice must never become a turn");
assert.match(turn.logs.join("\n"), /Ignoring my own voice/);

// You talking over her does become a turn.
turn.pending = "stop, call Rahul instead";
turn.scheduleLiveCommit();
await settle();
assert.equal(turn.sent.length, 2);
assert.equal(turn.sent[1].text, "stop, call Rahul instead");

// Interim words are enough: a turn commits even if no final result ever arrives.
turn.speaking = false;
turn.resetLiveTurn();
turn.interim = "remind me at five";
turn.scheduleLiveCommit();
await settle();
assert.equal(turn.sent.length, 3);
assert.equal(turn.sent[2].text, "remind me at five");

// The recognizer's own final for words a pause already committed is not a second turn,
// even when it arrives slightly corrected — but a genuine follow-up still is.
turn.resetLiveTurn();
turn.pending = "remind me at five pm";
turn.scheduleLiveCommit();
await settle();
assert.equal(turn.sent.length, 3, "a corrected repeat of the same breath must not be sent again");

turn.resetLiveTurn();
turn.pending = "and call Rahul";
turn.scheduleLiveCommit();
await settle();
assert.equal(turn.sent.length, 4, "a real follow-up sentence must still be sent");
assert.equal(turn.sent[3].text, "and call Rahul");

// --- wiring: the microphone really stays open ---------------------------------------
assert.match(orb, /void startVoiceRecognition\(\{ chat: true, continuous: true, mode: "live" \}\);/);
assert.match(
  orb,
  /sessionRecognition\.continuous = requestedMode === "wake" \|\| requestedMode === "live" \? true : continuous;/,
);
// Live mode must not take the branch that closes the microphone after one turn.
assert.match(orb, /function finishVoiceTurn\(\) \{\s*if \(voiceSessionMode !== "turn"\) return;/);
// And it must reopen at once instead of waiting for her voice to finish.
assert.match(orb, /const keepLive = voiceSessionMode === "live";/);
assert.match(
  orb,
  /if \(!keepLive && !keepWakeListening && window\.speechSynthesis && window\.speechSynthesis\.speaking\)/,
);
assert.match(orb, /liveRestartTimer = setTimeout\(restart, keepLive \? 20 : 40\);/);
// A dropped recognizer reopens rather than silently ending the session.
assert.match(orb, /liveRestartStorm \+= 1;/);
assert.match(orb, /if \(liveRestartStorm > 40\) \{/);

// --- wiring: echo is filtered before a turn is ever taken ---------------------------
// Her own voice is dropped once, early — before the misheard check can be fooled by a
// low-confidence echo and rotate the listening language away from yours.
assert.match(
  orb,
  /if \(voiceSessionMode === "live" && heardOwnVoice\(transcript\)\) \{\s*logEchoDropped\(transcript\);\s*liveBargeInSince = 0;\s*return;\s*\}/,
);
// Interim words are filtered before they reach the input box, so her own voice never even
// flashes on screen as though you had said it.
assert.match(orb, /if \(heardOwnVoice\(interim\)\) \{ logEchoDropped\(interim\); liveBargeInSince = 0; return; \}/);
assert.ok(
  orb.indexOf("if (heardOwnVoice(interim))") < orb.indexOf("liveInterim = interim.trim();"),
  "echo must be filtered before the interim text is stored or shown",
);
assert.match(orb, /noteSpokenForEcho\(clean\);/);
assert.match(orb, /utterance\.onstart = \(\) => \{/);
assert.match(orb, /utterance\.onend = voiceFinished;/);
assert.match(orb, /echoCancellation: true, noiseSuppression: true, autoGainControl: true/);

// --- wiring: she answers the moment you stop, and you can talk over her --------------
assert.match(orb, /const LIVE_SILENCE_MS = 620;/);
assert.match(orb, /function scheduleLiveCommit\(\)/);
assert.match(orb, /async function commitLiveTurn\(\)/);
assert.match(orb, /const LIVE_BARGE_IN_MS = 180;/);
assert.match(orb, /stopSpeakingForBargeIn\(\);\s*liveBargeInSince = 0;/);
// Interrupting her also relaxes the echo gate, so the rest of your sentence is not judged
// against words she was cut off in the middle of.
assert.match(orb, /function stopSpeakingForBargeIn\(\) \{\s*interruptAssistantSpeech\(\);\s*liveEchoUntil = Date\.now\(\) \+ 150;\s*liveSpeakingNow = "";/);
assert.equal(orb.split("stopSpeakingForBargeIn();").length - 1, 2, "both barge-in paths use it");
// The interruption is latched, so the rest of your sentence is not thrown away and she is
// not interrupted twice for one turn.
assert.match(orb, /if \(sheIsSpeaking\(\) && !liveBargedIn\) \{/);
assert.match(orb, /let liveBargedIn = false;/);
assert.match(orb, /liveBargedIn = false;\s*clearLiveCommitTimer\(\);/);
// Echo is dropped before the misheard check can rotate the listening language.
assert.ok(
  orb.indexOf('if (voiceSessionMode === "live" && heardOwnVoice(transcript))') <
    orb.indexOf("if (looksMisheard(transcript, confidence))"),
  "echo must be filtered before the misheard-language rotation",
);
// Her reply is spoken sentence by sentence as it streams, not after the whole answer.
assert.match(orb, /function createLiveSpeaker\(\)/);
assert.match(orb, /speakAppend\(sentence\);/);

// --- honest labels ------------------------------------------------------------------
assert.match(orb, /id="voiceBtn"[^>]*>LIVE VOICE<\/button>/);
assert.match(orb, /requestedMode === "live" \? 'LIVE VOICE ON' : 'VOICE ON'/);
assert.match(orb, /Live voice is on\. The microphone stays open while I speak/);
assert.match(orb, /Ignoring my own voice/);
// Nothing may claim the microphone closes after each turn while live mode is on.
assert.doesNotMatch(orb, /voiceSessionMode === "live"[^;]*finishVoiceTurn/s);

console.log("live voice echo filter, open-microphone wiring, and barge-in checks passed");
