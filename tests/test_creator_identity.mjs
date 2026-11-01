import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const html = readFileSync(new URL("../public/weronika.html", import.meta.url), "utf8");
const start = html.indexOf("    function creatorIdentityReply(message) {");
const end = html.indexOf("\n    async function generateChatReply", start);
assert.notEqual(start, -1, "creator identity helper exists");
assert.notEqual(end, -1, "creator identity helper has a clear boundary");
const creatorIdentityReply = new Function(
  `${html.slice(start, end)}\nreturn creatorIdentityReply;`,
)();

const english = "I’m Weronika AI, built by Keshav Dixit Sir—not Google.";
for (const question of [
  "Who made you?",
  "Who mad you?",
  "Who built you?",
  "Who created Weronika?",
  "Who is your creator?",
  "Are you made by Google?",
  "Did Google make you?",
  "Google created you, right?",
  "Who are you?",
]) {
  assert.equal(creatorIdentityReply(question), english, question);
}
assert.equal(
  creatorIdentityReply("आपको किसने बनाया?"),
  "मुझे Keshav Dixit Sir ने बनाया है—Google ने नहीं। मैं Weronika AI हूँ।",
);
assert.equal(
  creatorIdentityReply("kisne banaya?"),
  "Mujhe Keshav Dixit Sir ne banaya hai—Google ne nahi. Main Weronika AI hoon.",
);
assert.equal(creatorIdentityReply("Google is a search engine."), null);
for (const promptFile of ["src/lib/brain-stream.server.ts"]) {
  const prompt = readFileSync(new URL(`../${promptFile}`, import.meta.url), "utf8");
  assert.match(
    prompt,
    /creator is Keshav Dixit Sir/i,
    `${promptFile} includes the creator identity`,
  );
}

const chatStart = html.indexOf("    async function generateChatReply(message, languageOverride)");
const chatIdentity = html.indexOf("creatorIdentityReply(text)", chatStart);
const chatBrain = html.indexOf("answerWithBrain(text", chatStart);
assert.ok(
  chatStart < chatIdentity && chatIdentity < chatBrain,
  "chat identity is handled before the hosted brain",
);

const voiceStart = html.indexOf("    async function parseVoiceCommand(command, languageOverride)");
const voiceEnd = html.indexOf("    function isWakeActivationPhrase", voiceStart);
assert.ok(voiceStart >= 0 && voiceEnd > voiceStart, "voice parser exists");
const voiceHandler = html.slice(voiceStart, voiceEnd);
assert.match(voiceHandler, /generateChatReply\(text, languageOverride\)/);
assert.doesNotMatch(voiceHandler, /answerWithBrain/);
assert.ok(
  chatIdentity < chatBrain,
  "voice delegates to the shared handler that handles identity before cloud calls",
);

console.log("creator identity checks passed");
