import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  LEGACY_HISTORY_KEY,
  MEMORY_KEY,
  MEMORY_LIMITS,
  PRIVATE_TURN,
  createMemory,
  describeAway,
  normalizeMemory,
} from "../public/weronika-memory.js";

// --- helpers ------------------------------------------------------------------------
function fakeStorage(quota = Infinity) {
  const data = new Map();
  return {
    data,
    getItem: (key) => (data.has(key) ? data.get(key) : null),
    setItem: (key, value) => {
      if (String(value).length > quota) throw new Error("QuotaExceededError");
      data.set(key, String(value));
    },
    removeItem: (key) => data.delete(key),
  };
}

function clock(start = Date.UTC(2026, 10, 10, 18, 0, 0)) {
  let value = start;
  const now = () => value;
  now.advance = (ms) => {
    value += ms;
  };
  return now;
}

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const formatTime = (at) => new Date(at).toISOString();

function open(storage, now, extra = {}) {
  let seed = 1;
  return createMemory({
    storage,
    now,
    formatTime,
    random: () => (seed = (seed * 9301 + 49297) % 233280) / 233280,
    ...extra,
  });
}

function chat(memory, now, count, label = "topic") {
  for (let index = 0; index < count; index += 1) {
    now.advance(MINUTE);
    memory.rememberExchange(`question ${label} ${index}`, `answer ${label} ${index}`);
  }
}

// --- a restart keeps the conversation -------------------------------------------------
{
  const storage = fakeStorage();
  const now = clock();
  const first = open(storage, now);
  const started = first.beginSession();
  assert.equal(started.returning, false, "a brand-new memory is not a returning session");
  assert.deepEqual(first.brainHistory(), [], "nothing is sent before anything was said");

  first.rememberExchange("My name is Keshav and I am building a robot arm.", "Nice to meet you!");
  now.advance(2 * MINUTE);
  first.rememberExchange("Remember that the demo is on Friday.", "Got it, Friday.");
  assert.equal(first.stats().turns, 4);
  // Same session: the turns are still verbatim, so no memory note is needed yet.
  assert.equal(first.memoryNote(), "");

  // The computer is shut down overnight; a new page load creates a fresh instance.
  now.advance(14 * HOUR);
  const second = open(storage, now);
  const resumed = second.beginSession();
  assert.equal(resumed.returning, true);
  assert.equal(resumed.turns, 4);
  assert.equal(resumed.lastUser, "Remember that the demo is on Friday.");
  assert.equal(resumed.lastAssistant, "Got it, Friday.");
  assert.equal(resumed.sessions, 2);
  assert.ok(resumed.awayMs > 13 * HOUR && resumed.awayMs <= 14 * HOUR, "away time spans the shutdown");

  const restored = second.recent();
  assert.deepEqual(
    restored.map((turn) => [turn.role, turn.content]),
    [
      ["user", "My name is Keshav and I am building a robot arm."],
      ["assistant", "Nice to meet you!"],
      ["user", "Remember that the demo is on Friday."],
      ["assistant", "Got it, Friday."],
    ],
    "the chat log can be restored word for word",
  );

  const history = second.brainHistory();
  assert.equal(history[0].role, "user");
  assert.match(history[0].content, /Weronika's memory/);
  assert.match(history[0].content, /previous session ended on/);
  assert.match(history[0].content, /no longer active/);
  assert.equal(history[1].role, "assistant");
  assert.equal(history[2].content, "My name is Keshav and I am building a robot arm.");
  assert.equal(history.at(-1).content, "Got it, Friday.");
}

// --- the old 20-message history is carried over on upgrade ---------------------------------
{
  const storage = fakeStorage();
  storage.setItem(
    LEGACY_HISTORY_KEY,
    JSON.stringify([
      { role: "user", content: "old question" },
      { role: "assistant", content: "old answer" },
      { role: "system", content: "ignored" },
      { nonsense: true },
    ]),
  );
  const memory = open(storage, clock());
  assert.deepEqual(
    memory.recent().map((turn) => turn.content),
    ["old question", "old answer"],
  );
  assert.equal(storage.getItem(LEGACY_HISTORY_KEY), null, "the legacy key is retired");
  assert.ok(storage.getItem(MEMORY_KEY), "the new store is written");
  assert.equal(memory.beginSession().returning, true);
}

// --- the brain window obeys the route's limits ----------------------------------------------
{
  const now = clock();
  const memory = open(fakeStorage(), now);
  memory.beginSession();
  chat(memory, now, 40);
  memory.rememberExchange("x".repeat(9000), "y".repeat(9000));
  const history = memory.brainHistory();
  assert.ok(history.length <= 20, "the server keeps at most 20 history items");
  for (const item of history) {
    assert.ok(item.content.length <= 4000, "each item fits the server's 4000-character limit");
    assert.ok(item.role === "user" || item.role === "assistant");
  }
  for (let index = 1; index < history.length; index += 1) {
    assert.notEqual(history[index].role, history[index - 1].role, "roles alternate");
  }
  assert.equal(history.at(-1).role, "assistant");
  // Older turns that no digest covers yet are still represented in the note.
  assert.match(history[0].content, /Earlier details not summarised yet/);
  assert.ok(history[0].content.length <= MEMORY_LIMITS.noteMaxChars);
}

// --- long-term digest ---------------------------------------------------------------------
{
  const storage = fakeStorage();
  const now = clock();
  const memory = open(storage, now);
  memory.beginSession();
  chat(memory, now, 4);
  assert.equal(memory.needsDigest(), false, "the newest turns are never digested yet");
  chat(memory, now, 7, "later");
  assert.equal(memory.needsDigest(), false, "a digest waits until a full batch is ready");
  chat(memory, now, 2, "newest");
  assert.equal(memory.needsDigest(), true);

  const job = memory.digestJob();
  assert.ok(job.prompt.length <= 8000, "a digest request fits the brain route's message limit");
  assert.match(job.prompt, /Update Weronika's long-term memory/);
  assert.match(job.prompt, /\(none yet\)/);
  assert.match(job.prompt, /User: question topic 0/);
  assert.match(job.prompt, /Weronika: answer topic 3/);
  assert.match(job.prompt, /Weronika: answer later 3/);
  assert.doesNotMatch(job.prompt, /question later 4/, "the newest turns stay out of the digest");
  assert.doesNotMatch(job.prompt, /newest/, "the newest turns stay out of the digest");

  assert.equal(memory.applyDigest(job, "   "), false, "an empty summary is rejected");
  assert.equal(memory.needsDigest(), false, "a failed digest backs off before retrying");
  now.advance(3 * MINUTE);
  assert.equal(memory.needsDigest(), true);

  const notes = "The user is Keshav. He is building a robot arm. The demo is on Friday.";
  assert.equal(memory.applyDigest(memory.digestJob(), `\`\`\`\n${notes}\n\`\`\``), true);
  assert.equal(memory.stats().digestChars, notes.length, "code fences around the notes are removed");
  assert.equal(memory.needsDigest(), false);
  assert.match(memory.memoryNote(), /What I remember:\nThe user is Keshav\./);

  // After many more turns the next job carries the existing notes forward.
  chat(memory, now, 10, "third");
  const next = memory.digestJob();
  assert.match(next.prompt, /The user is Keshav\./);
  assert.doesNotMatch(next.prompt, /question topic 0/, "digested turns are not sent again");

  // A reply that would lose most of the existing notes is refused.
  const long = `${notes} `.repeat(8).trim();
  assert.equal(memory.applyDigest(next, long), true);
  chat(memory, now, 10, "fourth");
  assert.equal(memory.applyDigest(memory.digestJob(), "Sure! What should I remember?"), false);
  assert.equal(memory.stats().digestChars, long.length, "the previous notes are kept");

  // The digest survives a restart.
  const reopened = open(storage, now);
  reopened.beginSession();
  assert.match(reopened.brainHistory()[0].content, /The user is Keshav\./);
}

{
  // Full notes, full loose notes, and long turns: the request still fits the route's limit,
  // and every waiting turn is covered over a few requests.
  const now = clock();
  const memory = open(fakeStorage(), now, { limits: { maxTurns: 40 } });
  memory.beginSession();
  for (let index = 0; index < 30; index += 1) {
    now.advance(MINUTE);
    memory.rememberExchange(`early ${index} ${"e".repeat(200)}`, `reply ${index} ${"r".repeat(200)}`);
  }
  assert.equal(memory.applyDigest(memory.digestJob(), "n".repeat(MEMORY_LIMITS.digestMaxChars)), true);
  for (let index = 0; index < 40; index += 1) {
    now.advance(MINUTE);
    memory.rememberExchange(`long ${index} ${"q".repeat(900)}`, `long answer ${index} ${"a".repeat(900)}`);
  }
  assert.ok(memory.snapshot().backlog.length > 800, "dropped turns filled the loose notes");
  let rounds = 0;
  let previousThrough = 0;
  for (let job = memory.digestJob(); job; job = memory.digestJob()) {
    assert.ok(job.prompt.length <= 8000, `digest request ${rounds} fits the 8000-character limit`);
    assert.ok(job.count >= 6, "each request still carries a useful batch");
    assert.ok(job.through > previousThrough, "each request moves forward");
    previousThrough = job.through;
    assert.equal(memory.applyDigest(job, "n".repeat(MEMORY_LIMITS.digestMaxChars)), true);
    rounds += 1;
    assert.ok(rounds < 20, "digesting must finish");
  }
  assert.ok(rounds >= 2, "long conversations are folded in over several requests");
  assert.equal(memory.needsDigest(), false);
}

// --- storage limits never lose the thread ---------------------------------------------------
{
  const now = clock();
  const memory = open(fakeStorage(), now, { limits: { maxTurns: 12 } });
  memory.beginSession();
  chat(memory, now, 10, "robot");
  assert.equal(memory.stats().turns, 12);
  assert.match(memory.memoryNote(), /User: question robot 0/, "dropped turns leave a short trace");
  assert.match(memory.digestJob().prompt, /Earlier loose notes:/);
}

{
  // A browser that refuses large writes: memory shrinks instead of failing silently.
  const storage = fakeStorage(2600);
  const now = clock();
  const memory = open(storage, now);
  chat(memory, now, 30, "quota");
  const stats = memory.stats();
  assert.equal(stats.storageFailed, false);
  assert.ok(stats.turns < 60 && stats.turns >= 2, "older turns were dropped to fit");
  const reopened = open(storage, now);
  assert.equal(reopened.stats().turns, stats.turns, "what fits is what comes back");
  assert.equal(reopened.recent().at(-1).content, "answer quota 29", "the newest turn always survives");
}

{
  // Storage that refuses every write: the session keeps its conversation in RAM.
  const storage = fakeStorage(0);
  const now = clock();
  const memory = open(storage, now);
  chat(memory, now, 15, "ram");
  assert.equal(memory.stats().storageFailed, true);
  assert.equal(memory.stats().persistent, false);
  assert.equal(memory.stats().turns, 30, "nothing is thrown away when shrinking cannot help");
  assert.equal(memory.brainHistory().at(-1).content, "answer ram 14");
}

{
  // No storage at all (private mode): memory still works for the session.
  const memory = open(null, clock());
  memory.rememberExchange("hello", "hi");
  assert.equal(memory.stats().persistent, false);
  assert.equal(memory.brainHistory().length, 2);
}

// --- private local steps leave no content -----------------------------------------------------
{
  const storage = fakeStorage();
  const now = clock();
  const memory = open(storage, now);
  memory.rememberExchange("hello", "hi there");
  assert.equal(memory.rememberPrivate(), true);
  assert.equal(memory.rememberPrivate(), false, "consecutive private steps share one marker");
  const stored = storage.getItem(MEMORY_KEY);
  assert.ok(stored.includes(PRIVATE_TURN.user));
  assert.equal(memory.recent().filter((turn) => turn.kind === "private").length, 2);
  chat(memory, now, 12, "after");
  assert.doesNotMatch(memory.digestJob().prompt, /local messaging/, "markers are not digested");
}

// --- workspace statements are labelled for the brain -------------------------------------------
{
  const memory = open(fakeStorage(), clock());
  memory.rememberExchange("build a snake game", "Delivered 3 files to Workspace.", {
    src: "workspace",
  });
  const history = memory.brainHistory();
  assert.equal(history[0].content, "[Sent from the Workspace code editor] build a snake game");
  assert.equal(memory.recent()[0].src, "workspace");
  assert.equal(memory.lastUserContent(), "build a snake game");
}

// --- forgetting -----------------------------------------------------------------------------
{
  const storage = fakeStorage();
  const now = clock();
  const memory = open(storage, now);
  chat(memory, now, 3);
  assert.equal(memory.forgetContent("question topic 1"), true);
  assert.equal(memory.forgetContent("never said"), false);
  assert.equal(memory.stats().turns, 5);

  now.advance(MINUTE);
  memory.clear();
  assert.equal(memory.stats().turns, 0);
  assert.equal(memory.memoryNote(), "");
  assert.equal(open(storage, now).stats().turns, 0, "a clear survives a restart");

  // Switching memory off stores nothing but the switch.
  memory.rememberExchange("after clear", "ok");
  memory.setEnabled(false);
  assert.equal(memory.isEnabled(), false);
  memory.rememberExchange("secret", "still answered");
  assert.equal(memory.brainHistory().length, 2, "the session keeps its short-term context");
  assert.doesNotMatch(storage.getItem(MEMORY_KEY), /secret|after clear/);
  const reopened = open(storage, now);
  assert.equal(reopened.isEnabled(), false, "the switch itself is remembered");
  assert.equal(reopened.stats().turns, 0);
  assert.equal(reopened.beginSession().returning, false);
  assert.equal(reopened.needsDigest(), false);
  assert.deepEqual(reopened.merge({ v: 1, turns: [{ id: "x", role: "user", content: "old", at: 5 }] }), {
    changed: false,
    remoteStale: false,
  });
  assert.equal(reopened.stats().turns, 0, "a switched-off memory does not pull a copy back in");
}

// --- two copies of the memory (browser storage and the worker's file) ----------------------------
{
  const now = clock();
  const browser = open(fakeStorage(), now);
  const worker = open(fakeStorage(), now);
  chat(browser, now, 2, "browser");
  chat(worker, now, 2, "worker");

  let result = browser.merge(worker.snapshot());
  assert.deepEqual(result, { changed: true, remoteStale: true });
  assert.equal(browser.stats().turns, 8, "turns from both copies are united");
  const order = browser.recent().map((turn) => turn.at);
  assert.deepEqual(order, [...order].sort((a, b) => a - b), "merged turns stay in time order");

  result = browser.merge(browser.snapshot());
  assert.deepEqual(result, { changed: false, remoteStale: false }, "merging is idempotent");

  // A wipe on one copy is not undone by the stale other copy.
  const stale = browser.snapshot();
  now.advance(MINUTE);
  browser.clear();
  now.advance(MINUTE);
  browser.rememberExchange("fresh start", "hello again");
  result = browser.merge(stale);
  assert.equal(result.remoteStale, true, "the stale copy must be replaced");
  assert.deepEqual(
    browser.recent().map((turn) => turn.content),
    ["fresh start", "hello again"],
  );

  // An empty or unreadable remote copy just needs to be written.
  assert.deepEqual(browser.merge(null), { changed: false, remoteStale: true });
  assert.deepEqual(open(fakeStorage(), now).merge({ junk: true }), {
    changed: false,
    remoteStale: false,
  });

  // The newer long-term summary wins.
  const a = open(fakeStorage(), now);
  const b = open(fakeStorage(), now);
  chat(a, now, 12, "a");
  a.applyDigest(a.digestJob(), "Older notes about the user and the robot arm project.");
  b.merge(a.snapshot());
  chat(b, now, 12, "b");
  b.applyDigest(b.digestJob(), "Newer notes: the robot arm demo moved to Monday at ten.");
  a.merge(b.snapshot());
  assert.match(a.memoryNote(), /Newer notes/);
}

// --- switching memory off also wipes the other copy ---------------------------------------------
{
  const now = clock();
  const browser = open(fakeStorage(), now);
  const other = open(fakeStorage(), now); // another browser on the same computer
  chat(browser, now, 2, "before");
  other.merge(browser.snapshot());
  assert.equal(browser.wipeFor(browser.snapshot()), null, "nothing is wiped while memory is on");

  now.advance(MINUTE);
  browser.setEnabled(false);
  const switchedOff = browser.snapshot();
  assert.equal(switchedOff.enabled, false);
  assert.deepEqual(switchedOff.turns, [], "a switched-off copy holds no conversation");
  assert.ok(switchedOff.clearedAt > 0, "but it carries the moment everything was forgotten");

  // Meanwhile the other browser kept talking and wrote the worker's memory file.
  now.advance(MINUTE);
  other.rememberExchange("said later elsewhere", "noted");
  const wipe = browser.wipeFor(other.snapshot());
  assert.ok(wipe, "the file has not seen the switch-off yet");
  assert.deepEqual(
    wipe.turns.map((turn) => turn.content),
    ["said later elsewhere", "noted"],
    "only what was said after the switch-off stays",
  );
  assert.equal(normalizeMemory(wipe).turns.length, 2, "the result is a valid memory document");
  assert.equal(browser.wipeFor(wipe), null, "an up-to-date file is left alone");
  assert.equal(browser.stats().turns, 0, "the switched-off copy still stores nothing");
  assert.equal(browser.wipeFor(null), null);
  assert.equal(browser.wipeFor({ junk: true }), null);

  // The other browser adopts the wipe and keeps only what came after it.
  other.merge(wipe);
  assert.deepEqual(
    other.recent().map((turn) => turn.content),
    ["said later elsewhere", "noted"],
  );
  // The switch-off snapshot alone has the same effect on a copy that still holds old turns.
  const earlier = clock(Date.UTC(2026, 10, 10, 17, 0, 0));
  const third = open(fakeStorage(), earlier);
  chat(third, earlier, 1, "old");
  assert.equal(third.stats().turns, 2);
  third.merge(switchedOff);
  assert.equal(third.stats().turns, 0, "turns from before the switch-off are forgotten everywhere");
  assert.equal(third.isEnabled(), true, "each browser keeps its own switch");
}

// --- backup and restore -----------------------------------------------------------------------
{
  const now = clock();
  const memory = open(fakeStorage(), now);
  chat(memory, now, 3, "backup");
  const backup = JSON.parse(JSON.stringify(memory.exportData()));
  assert.equal(backup.app, "weronika-ai");
  assert.equal(backup.kind, "memory");
  assert.equal(backup.memory.turns.length, 6);

  now.advance(HOUR);
  memory.clear();
  assert.equal(memory.importData({ nope: 1 }), -1, "junk is refused");
  assert.equal(memory.importData("text"), -1);
  assert.equal(memory.importData(backup), 6, "a backup restores turns older than the wipe");
  assert.equal(memory.isEnabled(), true);

  // The restored copy now wins over a stale copy of the cleared state.
  const other = open(fakeStorage(), now);
  other.merge(memory.snapshot());
  assert.equal(other.stats().turns, 6);
}

// --- untrusted data ----------------------------------------------------------------------------
{
  assert.equal(normalizeMemory(null), null);
  assert.equal(normalizeMemory([]), null);
  assert.equal(normalizeMemory({ v: 2, turns: [] }), null);
  const cleaned = normalizeMemory({
    v: 1,
    turns: [
      { id: "b", role: "assistant", content: "second", at: 20 },
      { id: "a", role: "user", content: "first", at: 10, src: "workspace", extra: "dropped" },
      { id: "a", role: "user", content: "duplicate id", at: 30 },
      { id: "c", role: "system", content: "wrong role", at: 40 },
      { id: "d", role: "user", content: "   ", at: 50 },
      { id: "e", role: "user", content: "no time" },
      { id: "", role: "user", content: "no id", at: 60 },
      "junk",
    ],
    digest: 42,
    sessions: -5,
  });
  assert.deepEqual(cleaned.turns, [
    { id: "a", role: "user", content: "first", at: 10, src: "workspace" },
    { id: "b", role: "assistant", content: "second", at: 20 },
  ]);
  assert.equal(cleaned.digest, "");
  assert.equal(cleaned.sessions, 0);

  const storage = fakeStorage();
  storage.setItem(MEMORY_KEY, "{not json");
  assert.equal(open(storage, clock()).stats().turns, 0, "a corrupt store starts clean");
}

assert.equal(describeAway(20_000), "moments");
assert.equal(describeAway(5 * MINUTE), "5 minutes");
assert.equal(describeAway(HOUR), "1 hour");
assert.equal(describeAway(49 * HOUR), "2 days");

// --- the module stays on the device ---------------------------------------------------------------
const source = readFileSync(new URL("../public/weronika-memory.js", import.meta.url), "utf8");
assert.doesNotMatch(source, /\bfetch\(|XMLHttpRequest|WebSocket|sendBeacon|https?:\/\//);

console.log("on-device memory checks passed");
