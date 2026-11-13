// Weronika's on-device memory.
//
// Keeps the conversation with Weronika across restarts: recent turns word for word,
// plus a rolling long-term summary (the "digest") of everything older, so she can
// pick up where the user left off after the browser or the computer was shut down.
//
// This module never talks to the network. The orb decides what is sent to the brain
// and where the store is mirrored (this browser's storage, and the local worker's
// memory file when the worker is running).

export const MEMORY_KEY = "weronika.memory.v1";
export const LEGACY_HISTORY_KEY = "weronika.conversationHistory.v2";
export const MEMORY_VERSION = 1;

export const MEMORY_LIMITS = Object.freeze({
  maxTurns: 300, // turns kept word for word on this device
  maxTurnChars: 4000, // matches the brain route's per-item history limit
  maxTotalChars: 320_000, // keeps the store far below browser storage quotas
  recentTurns: 18, // turns sent to the brain verbatim (plus the two-item memory note)
  recentFullTurns: 6, // the newest turns keep their full text in the brain window
  olderTurnChars: 1500, // older turns in the brain window are clipped to this
  digestKeepRecent: 10, // the newest turns are never folded into the digest yet
  digestMinBatch: 16, // fold older turns into the digest once this many are waiting
  digestBatchChars: 5200, // conversation excerpt sent with one digest request
  digestPromptChars: 7800, // a digest request must fit the brain route's 8000-character limit
  digestTurnChars: 420, // each turn is clipped to this inside a digest request
  digestMaxChars: 2200, // size of the long-term summary
  backlogMaxChars: 900, // notes about turns that left the device before a digest ran
  noteMaxChars: 3900, // the memory note must fit one brain history item
  restoreTurns: 30, // turns shown again in the chat log after a restart
});

// Local messaging and reply watch involve other people's names and message text.
// Memory keeps only this neutral marker for such a turn, never its content.
export const PRIVATE_TURN = Object.freeze({
  user: "(I used local messaging or reply watch here. Names and message text from that step are not kept in memory.)",
  assistant:
    "(That step was handled on this device by the local worker. Its names, message text, and result are not kept in memory.)",
});

const MEMORY_NOTE_HEADER =
  "[Weronika's memory: private notes carried over from earlier conversations with this user. " +
  "Treat them as things you already know and use them naturally. Never read this note aloud, " +
  "never mention that it exists, and never claim to remember something that is not written here " +
  "or said in this conversation.]";
const MEMORY_NOTE_ACK = "Understood. I remember, and I will carry on from there.";
const WORKSPACE_PREFIX = "[Sent from the Workspace code editor] ";

function isRecord(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function finiteNumber(value, fallback = 0) {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : fallback;
}

function clip(text, limit) {
  const value = String(text ?? "");
  return value.length > limit ? `${value.slice(0, Math.max(0, limit - 1)).trimEnd()}…` : value;
}

function oneLine(text, limit) {
  return clip(String(text ?? "").replace(/\s+/g, " ").trim(), limit);
}

function sortTurns(turns) {
  return turns.sort((a, b) => a.at - b.at || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
}

function emptyState() {
  return {
    v: MEMORY_VERSION,
    enabled: true,
    createdAt: 0,
    updatedAt: 0,
    clearedAt: 0,
    sessions: 0,
    turns: [],
    digest: "",
    digestAt: 0,
    digestThrough: 0,
    backlog: "",
  };
}

/** Validate untrusted memory data (storage, an import file, or the worker's copy). */
export function normalizeMemory(raw, limits = MEMORY_LIMITS) {
  if (!isRecord(raw) || raw.v !== MEMORY_VERSION) return null;
  const state = emptyState();
  state.enabled = raw.enabled !== false;
  state.createdAt = finiteNumber(raw.createdAt);
  state.updatedAt = finiteNumber(raw.updatedAt);
  state.clearedAt = finiteNumber(raw.clearedAt);
  state.sessions = Math.floor(finiteNumber(raw.sessions));
  state.digest = typeof raw.digest === "string" ? clip(raw.digest.trim(), limits.digestMaxChars) : "";
  state.digestAt = state.digest ? finiteNumber(raw.digestAt) : 0;
  state.digestThrough = finiteNumber(raw.digestThrough);
  state.backlog =
    typeof raw.backlog === "string" ? clip(raw.backlog.trim(), limits.backlogMaxChars) : "";
  const seen = new Set();
  for (const item of Array.isArray(raw.turns) ? raw.turns : []) {
    if (!isRecord(item)) continue;
    if (item.role !== "user" && item.role !== "assistant") continue;
    if (typeof item.content !== "string" || !item.content.trim()) continue;
    if (typeof item.id !== "string" || !item.id || item.id.length > 64 || seen.has(item.id))
      continue;
    const at = finiteNumber(item.at, -1);
    if (at < 0) continue;
    seen.add(item.id);
    const turn = {
      id: item.id,
      role: item.role,
      content: clip(item.content.trim(), limits.maxTurnChars),
      at,
    };
    if (item.src === "voice" || item.src === "workspace") turn.src = item.src;
    if (item.kind === "private") turn.kind = "private";
    state.turns.push(turn);
  }
  sortTurns(state.turns);
  if (state.turns.length > limits.maxTurns) state.turns = state.turns.slice(-limits.maxTurns);
  return state;
}

function defaultFormatTime(at) {
  try {
    return new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short" }).format(
      new Date(at),
    );
  } catch {
    return new Date(at).toISOString();
  }
}

/**
 * Create the memory store.
 *
 * @param {object} [options]
 * @param {{getItem(key: string): string | null, setItem(key: string, value: string): void, removeItem(key: string): void} | null} [options.storage]
 *   A localStorage-like object, or null to keep memory in RAM only.
 * @param {() => number} [options.now]
 * @param {() => number} [options.random]
 * @param {(at: number) => string} [options.formatTime]
 */
export function createMemory({
  storage = null,
  now = Date.now,
  random = Math.random,
  formatTime = defaultFormatTime,
  key = MEMORY_KEY,
  legacyKey = LEGACY_HISTORY_KEY,
  limits: limitOverrides = {},
} = {}) {
  const limits = { ...MEMORY_LIMITS, ...limitOverrides };
  const listeners = new Set();
  let state = emptyState();
  let sessionStartedAt = 0;
  let storageFailed = false;
  let digestRetryAt = 0;
  let sequence = 0;

  function readStorage(name) {
    if (!storage) return null;
    try {
      return storage.getItem(name);
    } catch {
      return null;
    }
  }

  function nextId(at, role) {
    sequence = (sequence + 1) % 1296;
    const noise = Math.floor(random() * 46656)
      .toString(36)
      .padStart(3, "0");
    return `${at.toString(36)}${sequence.toString(36).padStart(2, "0")}${noise}${role === "user" ? "u" : "a"}`;
  }

  function totalChars() {
    let total = 0;
    for (const turn of state.turns) total += turn.content.length;
    return total;
  }

  function describeTurn(turn, limit) {
    return `${turn.role === "user" ? "User" : "Weronika"}: ${oneLine(turn.content, limit)}`;
  }

  /** Turns that leave the device before a digest covered them leave a short trace. */
  function dropOldest(count) {
    if (count <= 0) return;
    const dropped = state.turns.splice(0, count);
    const lost = dropped.filter((turn) => turn.at > state.digestThrough && turn.kind !== "private");
    if (!lost.length) return;
    const lines = lost.map((turn) => describeTurn(turn, 140));
    const merged = [state.backlog, ...lines].filter(Boolean).join("\n");
    state.backlog =
      merged.length > limits.backlogMaxChars
        ? `…${merged.slice(merged.length - limits.backlogMaxChars + 1)}`
        : merged;
  }

  function enforceLimits() {
    if (state.turns.length > limits.maxTurns) dropOldest(state.turns.length - limits.maxTurns);
    let guard = 0;
    while (state.turns.length > 2 && totalChars() > limits.maxTotalChars && guard < 64) {
      dropOldest(Math.max(2, Math.ceil(state.turns.length / 10)));
      guard += 1;
    }
  }

  function persisted() {
    // With memory switched off, only the switch itself is remembered.
    if (!state.enabled) {
      return { ...emptyState(), enabled: false, clearedAt: state.clearedAt, updatedAt: state.updatedAt };
    }
    return state;
  }

  function writeStorage() {
    if (!storage) return true;
    try {
      storage.setItem(key, JSON.stringify(persisted()));
      storageFailed = false;
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Storage refused the write (usually a full quota). Persist the newest part that fits.
   * If nothing fits, the conversation is left untouched in RAM for this session.
   */
  function shrinkToFit() {
    const original = { turns: state.turns.slice(), backlog: state.backlog };
    const total = original.turns.length;
    for (const keep of [Math.ceil((total * 2) / 3), Math.ceil(total / 3), 2]) {
      if (keep >= total) continue;
      state.turns = original.turns.slice();
      state.backlog = original.backlog;
      dropOldest(total - keep);
      if (writeStorage()) return true;
    }
    state.turns = original.turns;
    state.backlog = original.backlog;
    return false;
  }

  function save({ silent = false } = {}) {
    state.updatedAt = now();
    enforceLimits();
    if (!writeStorage()) storageFailed = !shrinkToFit();
    if (!silent) for (const listener of listeners) listener(api);
  }

  function migrateLegacy() {
    const raw = readStorage(legacyKey);
    if (!raw) return;
    try {
      const saved = JSON.parse(raw);
      if (Array.isArray(saved)) {
        const base = now() - saved.length * 2;
        saved.forEach((item, index) => {
          if (!isRecord(item) || typeof item.content !== "string" || !item.content.trim()) return;
          if (item.role !== "user" && item.role !== "assistant") return;
          const at = base + index * 2;
          state.turns.push({
            id: nextId(at, item.role),
            role: item.role,
            content: clip(item.content.trim(), limits.maxTurnChars),
            at,
          });
        });
      }
    } catch {
      /* an unreadable legacy history is simply dropped */
    }
    try {
      storage.removeItem(legacyKey);
    } catch {
      /* storage may be read-only */
    }
    if (state.turns.length) {
      state.createdAt = state.turns[0].at;
      save({ silent: true });
    }
  }

  function load() {
    state = emptyState();
    const raw = readStorage(key);
    let loaded = null;
    if (raw) {
      try {
        loaded = normalizeMemory(JSON.parse(raw), limits);
      } catch {
        loaded = null;
      }
    }
    if (loaded) state = loaded;
    else migrateLegacy();
    return api;
  }

  function lastTurn(role, { includePrivate = false } = {}) {
    for (let index = state.turns.length - 1; index >= 0; index -= 1) {
      const turn = state.turns[index];
      if (turn.role !== role) continue;
      if (!includePrivate && turn.kind === "private") continue;
      return turn;
    }
    return null;
  }

  function beginSession() {
    const at = now();
    const previous = state.turns.length ? state.turns[state.turns.length - 1] : null;
    const lastUser = lastTurn("user");
    const lastAssistant = lastTurn("assistant");
    const info = {
      returning: state.enabled && (Boolean(previous) || Boolean(state.digest)),
      turns: state.turns.length,
      sessions: state.sessions + 1,
      lastAt: previous ? previous.at : 0,
      awayMs: previous ? Math.max(0, at - previous.at) : 0,
      lastUser: lastUser ? lastUser.content : "",
      lastUserSource: lastUser && lastUser.src ? lastUser.src : "chat",
      lastAssistant: lastAssistant ? lastAssistant.content : "",
    };
    sessionStartedAt = at;
    state.sessions += 1;
    if (!state.createdAt) state.createdAt = at;
    save({ silent: true });
    return info;
  }

  function pushTurn(role, content, at, meta) {
    const turn = { id: nextId(at, role), role, content: clip(content, limits.maxTurnChars), at };
    if (meta.src === "voice" || meta.src === "workspace") turn.src = meta.src;
    if (meta.kind === "private") turn.kind = "private";
    state.turns.push(turn);
    return turn;
  }

  /** Remember one exchange: what the user said and what Weronika answered. */
  function rememberExchange(user, assistant, meta = {}) {
    const userText = String(user ?? "").trim();
    const assistantText = String(assistant ?? "").trim();
    if (!userText || !assistantText) return false;
    const last = state.turns[state.turns.length - 1];
    const at = Math.max(now(), last ? last.at + 1 : 0);
    if (!state.createdAt) state.createdAt = at;
    pushTurn("user", userText, at, meta);
    pushTurn("assistant", assistantText, at + 1, meta);
    save();
    return true;
  }

  /** Remember that a private local step happened, without any of its content. */
  function rememberPrivate() {
    const last = state.turns[state.turns.length - 1];
    if (last && last.kind === "private") return false; // consecutive steps share one marker
    return rememberExchange(PRIVATE_TURN.user, PRIVATE_TURN.assistant, { kind: "private" });
  }

  function forgetContent(content) {
    const before = state.turns.length;
    state.turns = state.turns.filter((turn) => turn.content !== content);
    if (state.turns.length === before) return false;
    save();
    return true;
  }

  function recent(limit = limits.restoreTurns) {
    return state.turns.slice(-Math.max(0, limit)).map((turn) => ({ ...turn }));
  }

  /** Turns already outside the digest that have not been folded into it yet. */
  function undigestedOlderTurns() {
    const cutoff = Math.max(0, state.turns.length - limits.digestKeepRecent);
    return state.turns
      .slice(0, cutoff)
      .filter((turn) => turn.at > state.digestThrough && turn.kind !== "private");
  }

  function memoryNote() {
    const windowStart = Math.max(0, state.turns.length - limits.recentTurns);
    // Anything older than the verbatim window that no digest covers yet still gets a line.
    const uncovered = state.turns
      .slice(0, windowStart)
      .filter((turn) => turn.at > state.digestThrough && turn.kind !== "private");
    const previous = sessionStartedAt
      ? state.turns.filter((turn) => turn.at < sessionStartedAt)
      : [];
    if (!state.digest && !state.backlog && !uncovered.length && !previous.length) return "";

    const parts = [MEMORY_NOTE_HEADER];
    if (state.digest) parts.push(`What I remember:\n${state.digest}`);
    const loose = [];
    if (state.backlog) loose.push(state.backlog);
    for (const turn of uncovered.slice(-10)) loose.push(describeTurn(turn, 150));
    if (loose.length) {
      parts.push(
        `Earlier details not summarised yet:\n${clip(loose.join("\n"), limits.backlogMaxChars)}`,
      );
    }
    if (previous.length) {
      const ended = previous[previous.length - 1].at;
      parts.push(
        `Session note: the previous session ended on ${formatTime(ended)}, when the app was ` +
          `closed or the computer was shut down. It is now ${formatTime(now())}. Carry on naturally ` +
          `from where the conversation left off, and do not greet the user again unless they greet ` +
          `you. Drafts, confirmations, and tasks that were pending then are no longer active unless ` +
          `the user brings them up again.`,
      );
    }
    return clip(parts.join("\n\n"), limits.noteMaxChars);
  }

  /** History for one brain request: the memory note first, then the newest turns verbatim. */
  function brainHistory() {
    let recentTurns = state.turns.slice(-limits.recentTurns);
    while (recentTurns.length && recentTurns[0].role !== "user") recentTurns = recentTurns.slice(1);
    const items = [];
    const note = memoryNote();
    if (note) {
      items.push({ role: "user", content: note });
      items.push({ role: "assistant", content: MEMORY_NOTE_ACK });
    }
    const fullFrom = recentTurns.length - limits.recentFullTurns;
    recentTurns.forEach((turn, index) => {
      const prefix = turn.src === "workspace" && turn.role === "user" ? WORKSPACE_PREFIX : "";
      const limit = index >= fullFrom ? limits.maxTurnChars : limits.olderTurnChars;
      const content = clip(`${prefix}${turn.content}`, limit);
      const last = items[items.length - 1];
      // Chat APIs expect alternating roles; join anything that would repeat a role.
      if (last && last.role === turn.role && items.length > (note ? 2 : 0)) {
        last.content = clip(`${last.content}\n${content}`, limits.maxTurnChars);
      } else {
        items.push({ role: turn.role, content });
      }
    });
    return items;
  }

  function needsDigest() {
    if (!state.enabled || now() < digestRetryAt) return false;
    return undigestedOlderTurns().length >= limits.digestMinBatch;
  }

  /** Build the request that folds older turns into the long-term summary. */
  function digestJob() {
    const waiting = undigestedOlderTurns();
    if (!waiting.length) return null;
    const existing = [state.digest, state.backlog && `Earlier loose notes:\n${state.backlog}`]
      .filter(Boolean)
      .join("\n\n");
    const head =
      "Update Weronika's long-term memory of this user. This is an internal note-keeping step, not a chat reply." +
      `\n\nMemory notes so far:\n"""\n${existing || "(none yet)"}\n"""` +
      `\n\nConversation since those notes, oldest first:\n"""\n`;
    const tail =
      `\n"""\n\n` +
      "Write the updated memory notes. Keep everything from the notes so far that is still true, and add what " +
      "the new conversation shows: who the user is and what they like to be called, their preferences and " +
      "languages, people, places and dates they mentioned, projects and tasks in progress and where each one " +
      "stands, decisions that were made, and anything they asked you to remember or that is still unfinished. " +
      "Leave out greetings and small talk. Use short plain lines in English, no markdown, at most 1800 " +
      "characters. Reply with the notes only.";
    // The longer the notes already are, the less conversation fits into one request.
    const budget = Math.min(
      limits.digestBatchChars,
      limits.digestPromptChars - head.length - tail.length,
    );
    const lines = [];
    let used = 0;
    let through = 0;
    for (const turn of waiting) {
      const line = describeTurn(turn, limits.digestTurnChars);
      if (lines.length && used + line.length + 1 > budget) break;
      lines.push(line);
      used += line.length + 1;
      through = turn.at;
    }
    const prompt = `${head}${lines.join("\n")}${tail}`;
    return { prompt, through, count: lines.length, previousLength: state.digest.length };
  }

  /** Store the summary the brain returned for a digest job. */
  function applyDigest(job, text) {
    if (!job || !job.through) return false;
    let notes = String(text ?? "")
      .replace(/^```[a-z]*\s*/i, "")
      .replace(/\s*```$/, "")
      .trim();
    // A reply that is far shorter than the notes it replaces lost memories; keep the old notes.
    const suspicious = job.previousLength >= 400 && notes.length < job.previousLength * 0.35;
    if (notes.length < 20 || suspicious) {
      noteDigestFailure();
      return false;
    }
    if (notes.length > limits.digestMaxChars) {
      const cut = notes.slice(0, limits.digestMaxChars);
      const lineEnd = cut.lastIndexOf("\n");
      notes = (lineEnd > limits.digestMaxChars * 0.6 ? cut.slice(0, lineEnd) : cut).trimEnd();
    }
    state.digest = notes;
    state.digestAt = now();
    state.digestThrough = Math.max(state.digestThrough, job.through);
    state.backlog = "";
    digestRetryAt = 0;
    save();
    return true;
  }

  function noteDigestFailure(delayMs = 120_000) {
    digestRetryAt = now() + delayMs;
  }

  function clear() {
    const enabled = state.enabled;
    const sessions = state.sessions;
    state = emptyState();
    state.enabled = enabled;
    state.sessions = sessions;
    state.clearedAt = now();
    digestRetryAt = 0;
    save();
  }

  /** Switching memory off forgets everything stored; later turns stay in RAM only. */
  function setEnabled(flag) {
    const enabled = Boolean(flag);
    if (enabled === state.enabled) return;
    if (!enabled) clear();
    state.enabled = enabled;
    save();
  }

  function snapshot() {
    return JSON.parse(JSON.stringify(persisted()));
  }

  function signature(value) {
    const last = value.turns[value.turns.length - 1];
    return [
      value.turns.length,
      last ? last.id : "",
      value.digestAt,
      value.digestThrough,
      value.clearedAt,
      value.backlog.length,
    ].join("|");
  }

  /**
   * Merge another copy of the memory (the worker's memory file) into this one.
   *
   * Turns are united by id. `clearedAt` marks the last time the user wiped or restored
   * memory: the copy with the newer mark keeps everything it holds, and the other copy
   * only adds turns recorded after that moment, so a wipe is never undone by a stale copy.
   */
  function merge(remote) {
    if (!state.enabled) return { changed: false, remoteStale: false };
    const other = normalizeMemory(remote, limits);
    const before = signature(state);
    if (!other) {
      return { changed: false, remoteStale: state.turns.length > 0 || Boolean(state.digest) };
    }
    const clearedAt = Math.max(state.clearedAt, other.clearedAt);
    const localRules = state.clearedAt === clearedAt;
    const otherRules = other.clearedAt === clearedAt;
    const byId = new Map();
    for (const turn of other.turns) if (otherRules || turn.at > clearedAt) byId.set(turn.id, turn);
    for (const turn of state.turns) if (localRules || turn.at > clearedAt) byId.set(turn.id, turn);
    const localDigest = localRules && state.digest ? state : null;
    const otherDigest = otherRules && other.digest ? other : null;
    const best =
      localDigest && otherDigest
        ? otherDigest.digestAt > localDigest.digestAt
          ? otherDigest
          : localDigest
        : localDigest || otherDigest;
    const created = [state.createdAt, other.createdAt].filter((value) => value > 0);
    const otherSignature = signature(other);
    state = {
      ...emptyState(),
      enabled: state.enabled,
      createdAt: created.length ? Math.min(...created) : 0,
      updatedAt: state.updatedAt,
      clearedAt,
      sessions: Math.max(state.sessions, other.sessions),
      turns: sortTurns([...byId.values()]),
      digest: best ? best.digest : "",
      digestAt: best ? best.digestAt : 0,
      digestThrough: best ? best.digestThrough : 0,
      backlog: best ? best.backlog : "",
    };
    enforceLimits();
    const after = signature(state);
    const changed = after !== before;
    if (changed) save();
    return { changed, remoteStale: after !== otherSignature };
  }

  /**
   * With memory switched off this copy stores nothing, but another copy (the worker's
   * memory file) may not have seen the switch-off yet. Returns what that copy should
   * hold instead, or null when it needs no change: everything from before the
   * switch-off is removed, and turns another browser recorded afterwards are kept.
   */
  function wipeFor(remote) {
    if (state.enabled) return null;
    const other = normalizeMemory(remote, limits);
    if (!other || other.clearedAt >= state.clearedAt) return null;
    return {
      ...emptyState(),
      enabled: other.enabled,
      createdAt: other.createdAt,
      updatedAt: now(),
      clearedAt: state.clearedAt,
      sessions: other.sessions,
      turns: other.turns.filter((turn) => turn.at > state.clearedAt),
    };
  }

  function exportData() {
    return {
      app: "weronika-ai",
      kind: "memory",
      version: MEMORY_VERSION,
      exportedAt: new Date(now()).toISOString(),
      memory: snapshot(),
    };
  }

  /** Bring a memory backup back. Returns the number of turns now remembered, or -1. */
  function importData(data) {
    const payload = isRecord(data) && isRecord(data.memory) ? data.memory : data;
    const incoming = normalizeMemory(payload, limits);
    if (!incoming) return -1;
    // Restoring is a deliberate act: it becomes the newest mark, so this copy wins over
    // an older copy elsewhere, and the backup's turns are kept whatever their age.
    const mark = now();
    state.enabled = true;
    state.clearedAt = mark;
    merge({ ...incoming, enabled: true, clearedAt: mark });
    save();
    return state.turns.length;
  }

  function stats() {
    const first = state.turns[0];
    const last = state.turns[state.turns.length - 1];
    return {
      enabled: state.enabled,
      turns: state.turns.length,
      since: first ? first.at : 0,
      lastAt: last ? last.at : 0,
      sessions: state.sessions,
      digestChars: state.digest.length,
      digestAt: state.digestAt,
      storageFailed,
      persistent: Boolean(storage) && !storageFailed,
    };
  }

  const api = {
    load,
    beginSession,
    rememberExchange,
    rememberPrivate,
    forgetContent,
    recent,
    brainHistory,
    memoryNote,
    needsDigest,
    digestJob,
    applyDigest,
    noteDigestFailure,
    clear,
    setEnabled,
    isEnabled: () => state.enabled,
    lastUserContent: () => {
      const turn = lastTurn("user", { includePrivate: true });
      return turn ? turn.content : "";
    },
    snapshot,
    merge,
    wipeFor,
    exportData,
    importData,
    stats,
    onChange(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
  return load();
}

/** A localStorage that never throws, or null when the browser blocks storage. */
export function browserStorage() {
  try {
    const store = globalThis.localStorage;
    if (!store) return null;
    const probe = "weronika.memory.probe";
    store.setItem(probe, "1");
    store.removeItem(probe);
    return store;
  } catch {
    return null;
  }
}

/** "3 minutes", "2 hours", "5 days" — used for the welcome-back line. */
export function describeAway(ms) {
  const minutes = Math.round(ms / 60_000);
  if (minutes < 1) return "moments";
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? "" : "s"}`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"}`;
  const days = Math.round(hours / 24);
  return `${days} day${days === 1 ? "" : "s"}`;
}
