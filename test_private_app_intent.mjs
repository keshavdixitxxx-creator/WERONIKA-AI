import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const html = readFileSync(new URL("./public/weronika.html", import.meta.url), "utf8");
const start = html.indexOf("    function detectPrivateAppRequest(message) {");
const end = html.indexOf("    async function answerPrivateAppRequest", start);
assert.notEqual(start, -1, "private app intent handler exists");
assert.notEqual(end, -1, "private app intent handler has a closing boundary");
const detectPrivateAppRequest = new Function(
  `${html.slice(start, end)}\nreturn detectPrivateAppRequest;`,
)();

assert.equal(
  detectPrivateAppRequest("From: Maya\nSubject: Roadmap\nThe deadline is Friday.").kind,
  "local_text",
);
assert.deepEqual(detectPrivateAppRequest("Summarize this email: The launch moved to Friday."), {
  kind: "local_text",
  task: "Summarize this email",
  content: "The launch moved to Friday.",
});
assert.deepEqual(detectPrivateAppRequest("Summarize my inbox"), {
  kind: "app",
  action: "read",
  app: "gmail",
  apps: ["gmail"],
  target: "",
  task: "Summarize my inbox",
});
assert.deepEqual(detectPrivateAppRequest("Read Gmail"), {
  kind: "app",
  action: "read",
  app: "gmail",
  apps: ["gmail"],
  target: "",
  task: "Read Gmail",
});
assert.deepEqual(detectPrivateAppRequest("Summarize WhatsApp messages from Mom"), {
  kind: "app",
  action: "read",
  app: "whatsapp",
  apps: ["whatsapp"],
  target: "Mom",
  task: "Summarize WhatsApp messages from Mom",
});
assert.equal(detectPrivateAppRequest("read Telegram channel Tech News").target, "Tech News");
assert.equal(detectPrivateAppRequest("reply to this WhatsApp message from Mom").recipient, "Mom");
assert.deepEqual(detectPrivateAppRequest("Draft a reply to the latest Outlook email"), {
  kind: "app",
  action: "prepare_send",
  app: "outlook",
  task: "Draft a reply to the latest Outlook email",
  send: false,
  mode: "reply",
  recipient: "",
  target: "",
  subject: "",
  content: "",
});
assert.equal(detectPrivateAppRequest("How do I draft an email?"), null);
assert.deepEqual(detectPrivateAppRequest("Private: Summarize: My appointment is Friday."), {
  kind: "local_text",
  task: "Summarize",
  content: "My appointment is Friday.",
});
assert.deepEqual(detectPrivateAppRequest("Private: My number is 123."), {
  kind: "local_text",
  task: "Summarize this private content",
  content: "My number is 123.",
});
assert.deepEqual(detectPrivateAppRequest("निजी: मेरी मीटिंग कल है।"), {
  kind: "local_text",
  task: "इस निजी सामग्री का सारांश दें",
  content: "मेरी मीटिंग कल है।",
});
assert.equal(detectPrivateAppRequest("मेरे व्हाट्सऐप संदेश"), null);
assert.deepEqual(
  detectPrivateAppRequest("सारांश मेरे व्हाट्सऐप संदेश: परिवार की यात्रा शुक्रवार को है"),
  {
    kind: "local_text",
    task: "सारांश मेरे व्हाट्सऐप संदेश",
    content: "परिवार की यात्रा शुक्रवार को है",
  },
);
assert.match(
  detectPrivateAppRequest("Summarize this:\nFrom: Maya\nSubject: Plan\nLet us meet.").content,
  /^From: Maya/,
);
assert.deepEqual(detectPrivateAppRequest("open Gmail"), {
  kind: "app",
  action: "open",
  app: "gmail",
  task: "open Gmail",
});
assert.equal(detectPrivateAppRequest("open Gmail and summarize my inbox").action, "read");
assert.equal(detectPrivateAppRequest("What does this email say?").app, "gmail");
assert.equal(detectPrivateAppRequest("What does this conversation say?").app, "whatsapp");
assert.equal(detectPrivateAppRequest("resume mi Gmail").action, "read");
assert.deepEqual(detectPrivateAppRequest("play Shape of You on Spotify"), {
  kind: "app",
  action: "play",
  app: "spotify",
  query: "Shape of You",
  task: "play Shape of You on Spotify",
});
assert.deepEqual(detectPrivateAppRequest("play Never Gonna Give You Up on YouTube"), {
  kind: "app",
  action: "play",
  app: "youtube",
  query: "Never Gonna Give You Up",
  task: "play Never Gonna Give You Up on YouTube",
});
assert.deepEqual(detectPrivateAppRequest("खोलो Gmail"), {
  kind: "app",
  action: "open",
  app: "gmail",
  task: "खोलो Gmail",
});
assert.deepEqual(detectPrivateAppRequest("open Outlook calendar"), {
  kind: "app",
  action: "open",
  app: "microsoft_calendar",
  task: "open Outlook calendar",
});
assert.equal(
  detectPrivateAppRequest("write an email to maya@example.com saying hello").recipient,
  "maya@example.com",
);
assert.deepEqual(
  detectPrivateAppRequest("send WhatsApp message to Mom saying: I will call at six"),
  {
    kind: "app",
    action: "prepare_send",
    app: "whatsapp",
    task: "send WhatsApp message to Mom saying: I will call at six",
    send: true,
    mode: "reply",
    recipient: "Mom",
    target: "",
    subject: "",
    content: "I will call at six",
  },
);
assert.deepEqual(detectPrivateAppRequest("check my Google Calendar today"), {
  kind: "app",
  action: "read",
  app: "google_calendar",
  apps: ["google_calendar"],
  target: "",
  task: "check my Google Calendar today",
});
assert.deepEqual(detectPrivateAppRequest("add a meeting to my Outlook calendar tomorrow at 3 PM"), {
  kind: "app",
  action: "calendar_create",
  app: "microsoft_calendar",
  task: "add a meeting to my Outlook calendar tomorrow at 3 PM",
});
assert.deepEqual(
  detectPrivateAppRequest("alert me about family messages on WhatsApp and Telegram"),
  {
    kind: "app",
    action: "start_family_alerts",
    apps: ["whatsapp", "telegram"],
    contacts: [],
    task: "alert me about family messages on WhatsApp and Telegram",
  },
);
assert.deepEqual(detectPrivateAppRequest("answer incoming Telegram call"), {
  kind: "app",
  action: "detect_call",
  app: "telegram",
  task: "answer incoming Telegram call",
});
assert.deepEqual(
  detectPrivateAppRequest("send WhatsApp message saying I will call later"),
  {
    kind: "app",
    action: "prepare_send",
    app: "whatsapp",
    task: "send WhatsApp message saying I will call later",
    send: true,
    mode: "reply",
    recipient: "",
    target: "",
    subject: "",
    content: "I will call later",
  },
  "ordinary message wording must not trigger call-answer flow",
);

const generateStart = html.indexOf("    async function generateChatReply");
const privateGuard = html.indexOf(
  "const privateRequest = detectPrivateAppRequest(message)",
  generateStart,
);
const cloudBrain = html.indexOf(
  "const brainReply = await answerWithBrain(message, languageOverride)",
  generateStart,
);
assert.ok(
  privateGuard > generateStart && privateGuard < cloudBrain,
  "private requests are gated before the cloud brain",
);
assert.match(html, /\/api\/local\/brain/, "private processing uses the local-agent route");
assert.match(html, /\/api\/apps\/action/, "signed-in app workflows use only the local agent route");

console.log("private app intent and workflow checks passed");
