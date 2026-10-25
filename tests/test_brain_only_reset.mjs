import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(new URL("..", import.meta.url).pathname);
const html = readFileSync(new URL("../public/weronika.html", import.meta.url), "utf8");
const viteConfig = readFileSync(new URL("../vite.config.ts", import.meta.url), "utf8");
const packageJson = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8"));

assert.equal(existsSync(resolve(root, "weronika-py")), false, "the legacy Python agent is removed");
for (const file of [
  "public/weronika-automation.js",
  "public/weronika-google.js",
  "public/weronika-memory.js",
  "public/weronika-same-browser.js",
  "public/weronika-workspace.js",
]) {
  assert.equal(existsSync(resolve(root, file)), false, `${file} is removed`);
}
assert.doesNotMatch(html, /api\/weronika-agent|127\.0\.0\.1:8765|api\/apps\/action|api\/google\/action/);
assert.doesNotMatch(viteConfig, /127\.0\.0\.1:8765|api\/weronika-agent/);
assert.doesNotMatch(JSON.stringify(packageJson.scripts), /python|sync:standalone|dev:py/);
assert.doesNotMatch(html, /Local PC automation|Same-browser automation|CONNECT GOOGLE|CODE WORKSPACE|PC CURSOR OFF/);

const chatStart = html.indexOf("    async function generateChatReply(message, languageOverride)");
const chatEnd = html.indexOf("    async function parseVoiceCommand", chatStart);
assert.ok(chatStart >= 0 && chatEnd > chatStart, "chat reply handler exists");
const chatHandler = html.slice(chatStart, chatEnd);
assert.match(chatHandler, /answerWithBrain\(text, languageOverride\)/);
assert.doesNotMatch(chatHandler, /fetch\(|openWebsite|searchWeb|postLocalAppAction|parsePcCommand/);

const voiceStart = chatEnd;
const voiceEnd = html.indexOf("    function isWakeActivationPhrase", voiceStart);
assert.ok(voiceEnd > voiceStart, "voice handler has a clear boundary");
const voiceHandler = html.slice(voiceStart, voiceEnd);
assert.match(voiceHandler, /answerWithBrain\(text, languageOverride\)/);
assert.doesNotMatch(voiceHandler, /fetch\(|openWebsite|searchWeb|postLocalAppAction|parsePcCommand/);

console.log("brain-only reset checks passed");
