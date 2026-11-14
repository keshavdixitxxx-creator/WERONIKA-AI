// Commands Weronika carries out herself, at once, without the cloud brain:
// opening apps, maps, music, Google shortcuts, the clock, alarms, timers, reminders,
// headlines. This file only reads the sentence and says what it means. It has no
// DOM and no network, so the tests import it directly.

const POLITE_RE =
  /^(?:(?:hey|hi|ok|okay|yo)[\s,]+)?(?:(?:weronika|veronika|veronica)[\s,!.]+)?(?:(?:can|could|will|would)\s+you\s+)?(?:(?:please|kindly|just)\s+)*/i;
const TAIL_RE = /[\s,]*(?:\bplease\b|\bfor me\b)?[\s.!?]*$/i;

export function cleanCommand(text) {
  const value = String(text || "")
    .replace(/\s+/g, " ")
    .trim()
    .replace(POLITE_RE, "");
  return value.replace(TAIL_RE, "").trim();
}

// --------------------------------------------------------------------- greeting
// What Weronika says aloud when the LAUNCH button is pressed.
export function launchGreeting({
  name = "",
  persona = "friendly",
  now = new Date(),
  returning = false,
  away = "",
} = {}) {
  const hour = now.getHours();
  const hello =
    hour < 5
      ? "Hello"
      : hour < 12
        ? "Good morning"
        : hour < 17
          ? "Good afternoon"
          : hour < 22
            ? "Good evening"
            : "Hello";
  const who = name ? `, ${name}` : "";
  if (persona === "romantic") {
    if (!returning)
      return `${hello}${who}. I'm Weronika, and from now on I'm yours. Tell me what you need, and consider it done.`;
    if (away)
      return `${hello}${who}. You were gone for ${away}, and I missed you. I'm right here now. What shall we do?`;
    return `${hello}${who}. I was hoping you'd come back. I'm right here. What shall we do?`;
  }
  if (persona === "professional") return `${hello}${who}. Weronika is online. How can I help?`;
  if (returning)
    return `${hello}${who}. Good to see you again. Weronika is online. What shall we do?`;
  return `${hello}${who}. I'm Weronika, online and ready. What shall we do?`;
}

// ----------------------------------------------------------------------- apps
// Spoken names that mean a program on the computer. The worker's own list
// (weronika-py/weronika_agent/apps.py) decides how each one is started; a test keeps
// the two in step. Names that are also websites ("calendar", "maps", "spotify")
// are not here: the worker picks the installed program or the site for those.
export const DESKTOP_APP_NAMES = [
  "notepad",
  "text editor",
  "calculator",
  "calc",
  "paint",
  "ms paint",
  "file explorer",
  "explorer",
  "files",
  "file manager",
  "this pc",
  "finder",
  "command prompt",
  "cmd",
  "terminal",
  "console",
  "powershell",
  "power shell",
  "task manager",
  "activity monitor",
  "system monitor",
  "settings",
  "system settings",
  "windows settings",
  "pc settings",
  "control panel",
  "snipping tool",
  "screenshot tool",
  "camera",
  "webcam",
  "clock",
  "alarm clock",
  "wordpad",
  "character map",
  "on screen keyboard",
  "on-screen keyboard",
  "virtual keyboard",
  "magnifier",
  "microsoft store",
  "app store",
  "chrome",
  "google chrome",
  "edge",
  "microsoft edge",
  "firefox",
  "brave",
  "opera",
  "vs code",
  "vscode",
  "visual studio code",
  "ms word",
  "microsoft word",
  "ms excel",
  "microsoft excel",
  "powerpoint",
  "power point",
  "onenote",
  "one note",
  "ms teams",
  "vlc",
  "vlc player",
  "discord",
  "zoom",
  "steam",
  "obs",
  "notion",
  "slack",
  "photoshop",
  "premiere",
  "blender",
  "android studio",
  "pycharm",
  "postman",
  "git bash",
];
const DESKTOP_APPS = new Set(DESKTOP_APP_NAMES);
const OPEN_RE = /^(?:open|launch|start|run|fire up|bring up)\s+(?:up\s+)?(.{1,160})$/i;
const OPEN_SPLIT_RE = /\s*(?:,|&|\band\b|\bthen\b|\balso\b|\bplus\b)\s*/i;
const APP_WORD_RE = /\s+(?:desktop\s+)?(?:app|application|program|software)$/i;
// Words that make a part of the list a task, not a name: "open chrome and search for …".
const NOT_A_NAME_RE =
  /\b(?:search|google|look|find|play|watch|read|comment|subscribe|like|summari[sz]e|result|results|page|link|tab|window|file|folder|in|on|with|using|for|to|it|this|that)\b/i;

// "open notepad", "open chrome and youtube", "open the spotify app". The sentence is
// taken only when it names at least one program; the other names in the same list go
// along, and the worker decides for each whether it is a program or a site.
function parseOpen(value) {
  const match = value.match(OPEN_RE);
  if (!match) return null;
  const parts = match[1]
    .split(OPEN_SPLIT_RE)
    .map((part) => part.trim())
    .filter(Boolean);
  if (!parts.length || parts.length > 5) return null;
  const targets = [];
  let programs = 0;
  for (const part of parts) {
    let name = part
      .replace(/^(?:the|my|a|an)\s+/i, "")
      .replace(/\.exe$/i, "")
      .trim();
    const marked = APP_WORD_RE.test(name);
    if (marked) name = name.replace(APP_WORD_RE, "").trim();
    if (!name || !/^[\p{L}\p{N} .+'#-]{1,60}$/u.test(name)) return null;
    const known = DESKTOP_APPS.has(name.toLowerCase());
    if (known || marked) programs += 1;
    else if (name.split(" ").length > 3 || NOT_A_NAME_RE.test(name)) return null;
    targets.push({ name, kind: marked ? "app" : "auto" });
  }
  return programs ? { kind: "open", targets } : null;
}

// --------------------------------------------------------------------- numbers
const NUMBER_WORDS = {
  a: 1,
  an: 1,
  one: 1,
  two: 2,
  three: 3,
  four: 4,
  five: 5,
  six: 6,
  seven: 7,
  eight: 8,
  nine: 9,
  ten: 10,
  eleven: 11,
  twelve: 12,
  fifteen: 15,
  twenty: 20,
  thirty: 30,
  forty: 40,
  "forty five": 45,
  "forty-five": 45,
  fifty: 50,
  sixty: 60,
  ninety: 90,
};
const NUMBER_WORD_SOURCE = Object.keys(NUMBER_WORDS)
  .sort((a, b) => b.length - a.length)
  .join("|");
const UNIT_SOURCE = "seconds?|secs?|sec|s|minutes?|mins?|min|m|hours?|hrs?|hr|h|days?|d";
// A number in digits may touch its unit ("90s"); a number word needs a space, so
// that the "an" + "d" of "and" is never read as "a day".
const AMOUNT_SOURCE = `(?:(?<![\\w.])(\\d+(?:\\.\\d+)?)\\s*|\\b(${NUMBER_WORD_SOURCE})\\s+)(${UNIT_SOURCE})\\b`;
const DURATION_PART_RE = new RegExp(AMOUNT_SOURCE, "gi");
const DURATION_SOURCE = `(?:${AMOUNT_SOURCE.replace(/\((?!\?)/g, "(?:")}(?:\\s*(?:,|and)?\\s*)?)+`;

function numberOf(word) {
  const key = String(word).toLowerCase();
  return key in NUMBER_WORDS ? NUMBER_WORDS[key] : Number(key);
}

function unitMs(unit) {
  const key = unit.toLowerCase();
  if (key.startsWith("s")) return 1000;
  if (key.startsWith("m")) return 60000;
  if (key.startsWith("h")) return 3600000;
  return 86400000;
}

// "half an hour", "an hour and a half", "2 and a half hours" in plain amounts.
function plainAmounts(value) {
  return value
    .replace(/\bhalf an? hour\b/gi, "30 minutes")
    .replace(/\b(?:an?|one) hour and a half\b/gi, "90 minutes")
    .replace(/\b(?:an?|one) and a half hours?\b/gi, "90 minutes")
    .replace(/\b(\d+) and a half hours?\b/gi, (_, hours) => `${Number(hours) * 60 + 30} minutes`)
    .replace(
      /\b(\d+) and a half minutes?\b/gi,
      (_, minutes) => `${Number(minutes) * 60 + 30} seconds`,
    )
    .replace(/\b(?:a )?quarter of an hour\b/gi, "15 minutes");
}

// "10 minutes", "1 hour 30 minutes", "an hour and a half", "90s" -> milliseconds.
export function parseDuration(text) {
  let value = String(text || "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
  if (!value) return null;
  value = plainAmounts(value);
  let total = 0;
  let found = false;
  const rest = value.replace(DURATION_PART_RE, (_, digits, word, unit) => {
    total += numberOf(digits ?? word) * unitMs(unit);
    found = true;
    return " ";
  });
  if (!found || !Number.isFinite(total) || total <= 0) return null;
  if (rest.replace(/\band\b|,/g, " ").trim()) return null; // something else was said
  return Math.round(total);
}

export function describeDuration(ms) {
  let seconds = Math.max(0, Math.round(ms / 1000));
  const parts = [];
  for (const [label, size] of [
    ["hour", 3600],
    ["minute", 60],
    ["second", 1],
  ]) {
    const amount = Math.floor(seconds / size);
    if (amount) parts.push(`${amount} ${label}${amount === 1 ? "" : "s"}`);
    seconds -= amount * size;
  }
  return parts.length ? parts.slice(0, 2).join(" ") : "0 seconds";
}

// ---------------------------------------------------------------------- dates
const WEEKDAYS = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"];
const MONTHS = [
  "january",
  "february",
  "march",
  "april",
  "may",
  "june",
  "july",
  "august",
  "september",
  "october",
  "november",
  "december",
];
const WEEKDAY_SOURCE =
  "sun(?:day)?|mon(?:day)?|tue(?:s|sday)?|wed(?:nesday)?|thu(?:r|rs|rsday)?|fri(?:day)?|sat(?:urday)?";
const MONTH_SOURCE =
  "jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?";

function startOfDay(date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function addDays(date, days) {
  return new Date(
    date.getFullYear(),
    date.getMonth(),
    date.getDate() + days,
    date.getHours(),
    date.getMinutes(),
    0,
    0,
  );
}

function validDate(year, month, day) {
  const date = new Date(year, month, day);
  return date.getFullYear() === year && date.getMonth() === month && date.getDate() === day
    ? date
    : null;
}

// Reads the day and the time out of a sentence. Returns null when it names neither.
//   at       the moment meant (a Date)
//   hasDate  a day was named      hasTime  a clock time was named
//   repeat   "daily" for "every day"
//   rest     the sentence without the day and time words
// With bareTime a lone number counts as an hour ("alarm for 6").
export function parseWhen(text, now = new Date(), options = {}) {
  let rest = ` ${plainAmounts(
    String(text || "")
      .replace(/\s+/g, " ")
      .trim(),
  )} `;
  const take = (pattern) => {
    const match = rest.match(pattern);
    if (match) rest = `${rest.slice(0, match.index)} ${rest.slice(match.index + match[0].length)}`;
    return match;
  };

  let repeat = "";
  if (
    take(
      /\b(?:every\s?day|daily|each day|every (?:single )?(?:morning|night|evening)|har din|roz(?:ana)?)\b/i,
    )
  )
    repeat = "daily";

  const relative = take(new RegExp(`\\b(?:in|after)\\s+(${DURATION_SOURCE})`, "i"));
  if (relative) {
    const ms = parseDuration(relative[1]);
    if (ms) {
      return {
        at: new Date(now.getTime() + ms),
        hasDate: true,
        hasTime: true,
        repeat,
        relative: true,
        rest: rest.replace(/\s+/g, " ").trim(),
      };
    }
  }

  let day = null;
  let partOfDay = "";
  let match;
  if (take(/\b(?:the\s+)?day after tomorrow\b|\bparso\b/i)) day = addDays(startOfDay(now), 2);
  else if (take(/\b(?:tomorrow|tmrw|tmr)\b/i)) day = addDays(startOfDay(now), 1);
  else if ((match = take(/\b(?:today|tonight|aaj)\b/i))) {
    day = startOfDay(now);
    if (/tonight/i.test(match[0])) partOfDay = "night";
  } else if (
    (match = take(new RegExp(`\\b(?:(?:on|this|next|coming)\\s+)*(${WEEKDAY_SOURCE})\\b`, "i")))
  ) {
    const wanted = WEEKDAYS.findIndex((name) =>
      name.startsWith(match[1].toLowerCase().slice(0, 3)),
    );
    const ahead = (wanted - now.getDay() + 7) % 7;
    day = addDays(startOfDay(now), ahead);
    day.sameWeekday = ahead === 0;
  } else if (
    (match = take(
      new RegExp(
        `\\b(?:on\\s+)?(?:the\\s+)?(\\d{1,2})(?:st|nd|rd|th)?\\s+(?:of\\s+)?(${MONTH_SOURCE})\\b\\.?(?:,?\\s+(\\d{4}))?`,
        "i",
      ),
    ))
  ) {
    day = namedDate(Number(match[1]), match[2], match[3], now);
  } else if (
    (match = take(
      new RegExp(
        `\\b(?:on\\s+)?(${MONTH_SOURCE})\\b\\.?\\s+(?:the\\s+)?(\\d{1,2})(?:st|nd|rd|th)?\\b(?:,?\\s+(\\d{4}))?`,
        "i",
      ),
    ))
  ) {
    day = namedDate(Number(match[2]), match[1], match[3], now);
  } else if ((match = take(/\b(?:on\s+)?(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b/))) {
    const year = match[3]
      ? match[3].length === 2
        ? 2000 + Number(match[3])
        : Number(match[3])
      : now.getFullYear();
    let date = validDate(year, Number(match[2]) - 1, Number(match[1]));
    if (date && !match[3] && date < startOfDay(now))
      date = validDate(year + 1, Number(match[2]) - 1, Number(match[1]));
    day = date;
    if (!day) return null;
  }

  const part = take(
    /\b(?:in the |this |at )?(morning|afternoon|evening|night|subah|dopahar|shaam|sham|raat)\b/i,
  );
  if (part) {
    const word = part[1].toLowerCase();
    partOfDay = /morning|subah/.test(word)
      ? "morning"
      : /afternoon|dopahar/.test(word)
        ? "afternoon"
        : /evening|sha+m/.test(word)
          ? "evening"
          : "night";
  }

  let hour = null;
  let minute = 0;
  let meridiem = "";
  if (take(/\b(?:at\s+|by\s+)?(?:12\s+)?(?:noon|midday)\b/i)) {
    hour = 12;
    meridiem = "pm";
  } else if (take(/\b(?:at\s+|by\s+)?(?:12\s+)?midnight\b/i)) {
    hour = 0;
    meridiem = "am";
    if (!day) day = addDays(startOfDay(now), 1);
    else if (partOfDay === "night") day = addDays(day, 1);
  } else if (
    (match = take(
      /(?:\b(?:at|by|for|around|about)\s+|@\s*)?\b(\d{1,2})(?:[:.](\d{2}))?\s*(a\.?m\.?|p\.?m\.?)(?![a-z])/i,
    ))
  ) {
    hour = Number(match[1]);
    minute = Number(match[2] || 0);
    meridiem = match[3].toLowerCase().startsWith("a") ? "am" : "pm";
  } else if ((match = take(/(?:\b(?:at|by|for|around|about)\s+|@\s*)?\b(\d{1,2}):(\d{2})\b/))) {
    hour = Number(match[1]);
    minute = Number(match[2]);
  } else if (
    (match = take(
      /(?:\b(?:at|by|around|about)\s+|@\s*)\b(\d{1,2})(?:\.(\d{2}))?(?:\s*(?:o['’]?clock|baje))?(?![\d:/-]|\s*(?:minutes?|mins?|hours?|hrs?|seconds?|secs?|days?|people|persons?|times|%|th\b|st\b|nd\b|rd\b))/i,
    ))
  ) {
    hour = Number(match[1]);
    minute = Number(match[2] || 0);
  } else if ((match = take(/\b(\d{1,2})(?:\.(\d{2}))?\s*(?:o['’]?clock|baje)\b/i))) {
    hour = Number(match[1]);
    minute = Number(match[2] || 0);
  } else if (
    options.bareTime &&
    (match = take(/(?:\b(?:for|to)\s+)?\b(\d{1,2})(?:\.(\d{2}))?\b(?![\d:/-])/))
  ) {
    hour = Number(match[1]);
    minute = Number(match[2] || 0);
  }

  if (hour === null && !day && !partOfDay) return null;
  if (hour !== null && (hour > 23 || minute > 59 || (meridiem && hour > 12))) return null;

  const cleaned = rest.replace(/\s+/g, " ").trim();
  if (hour === null) {
    const base = day || startOfDay(now);
    const defaults = { morning: 9, afternoon: 15, evening: 18, night: 21 };
    if (!partOfDay)
      return {
        at: new Date(base.getFullYear(), base.getMonth(), base.getDate(), 9, 0),
        hasDate: true,
        hasTime: false,
        repeat,
        rest: cleaned,
      };
    let at = new Date(base.getFullYear(), base.getMonth(), base.getDate(), defaults[partOfDay], 0);
    if (!day && at <= now) at = addDays(at, 1);
    return { at, hasDate: Boolean(day), hasTime: true, vague: true, repeat, rest: cleaned };
  }

  if (!meridiem && hour >= 1 && hour <= 12) {
    if (partOfDay === "morning") meridiem = "am";
    else if (partOfDay === "afternoon" || partOfDay === "evening") meridiem = "pm";
    else if (partOfDay === "night") meridiem = hour === 12 || hour <= 4 ? "am" : "pm";
  }
  const candidates = [];
  if (meridiem === "am") candidates.push(hour % 12);
  else if (meridiem === "pm") candidates.push((hour % 12) + 12);
  else if (hour === 0 || hour > 12) candidates.push(hour);
  else candidates.push(hour % 12, (hour % 12) + 12); // "at 6": the next six o'clock

  const base = day || startOfDay(now);
  const moments = candidates.map(
    (value) => new Date(base.getFullYear(), base.getMonth(), base.getDate(), value, minute),
  );
  let at;
  if (!day) {
    at = moments.find((moment) => moment > now) || addDays(moments[0], 1);
  } else if (day.sameWeekday) {
    at =
      moments.find((moment) => moment > now) ||
      addDays(moments[moments.length > 1 && moments[0].getHours() < 7 ? 1 : 0], 7);
  } else if (startOfDay(now).getTime() === startOfDay(day).getTime()) {
    at = moments.find((moment) => moment > now) || moments[moments.length - 1];
  } else {
    // A named day without am/pm: daytime is meant ("Friday at 5" is 5 pm, "at 9" is 9 am).
    at = moments.length > 1 ? (moments[0].getHours() >= 7 ? moments[0] : moments[1]) : moments[0];
  }
  return { at, hasDate: Boolean(day), hasTime: true, repeat, rest: cleaned };
}

function namedDate(dayNumber, monthWord, yearWord, now) {
  const month = MONTHS.findIndex((name) => name.startsWith(monthWord.toLowerCase().slice(0, 3)));
  const year = yearWord ? Number(yearWord) : now.getFullYear();
  let date = validDate(year, month, dayNumber);
  if (date && !yearWord && date < startOfDay(now)) date = validDate(year + 1, month, dayNumber);
  return date;
}

export function formatClock(date) {
  const hours = date.getHours();
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return `${hours % 12 || 12}:${minutes} ${hours < 12 ? "AM" : "PM"}`;
}

export function formatDay(date, now = new Date()) {
  const days = Math.round((startOfDay(date) - startOfDay(now)) / 86400000);
  if (days === 0) return "today";
  if (days === 1) return "tomorrow";
  const weekday = WEEKDAYS[date.getDay()].replace(/^./, (letter) => letter.toUpperCase());
  if (days > 1 && days < 7) return `on ${weekday}`;
  const month = MONTHS[date.getMonth()].replace(/^./, (letter) => letter.toUpperCase());
  const year = date.getFullYear() === now.getFullYear() ? "" : ` ${date.getFullYear()}`;
  return `on ${weekday}, ${date.getDate()} ${month}${year}`;
}

export function formatMoment(date, now = new Date()) {
  return `${formatClock(date)} ${formatDay(date, now)}`;
}

export function formatFullDate(date) {
  const weekday = WEEKDAYS[date.getDay()].replace(/^./, (letter) => letter.toUpperCase());
  const month = MONTHS[date.getMonth()].replace(/^./, (letter) => letter.toUpperCase());
  return `${weekday}, ${date.getDate()} ${month} ${date.getFullYear()}`;
}

// ----------------------------------------------------------------------- links
const encode = (value) => encodeURIComponent(String(value || "").trim());

export function mapsSearchUrl(place) {
  return `https://www.google.com/maps/search/?api=1&query=${encode(place)}`;
}

export function mapsDirectionsUrl(destination, origin = "") {
  const from = String(origin || "").trim();
  return `https://www.google.com/maps/dir/?api=1&destination=${encode(destination)}${from ? `&origin=${encode(from)}` : ""}`;
}

export function youtubeSearchUrl(query) {
  return `https://www.youtube.com/results?search_query=${encode(query)}`;
}

export function spotifySearchUrl(query) {
  return `https://open.spotify.com/search/${encode(query)}`;
}

function stamp(date, withTime) {
  const pad = (value) => String(value).padStart(2, "0");
  const day = `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}`;
  return withTime ? `${day}T${pad(date.getHours())}${pad(date.getMinutes())}00` : day;
}

// A Google Calendar "new event" page with the fields filled in. Nothing is saved
// until the user presses Save there. Times are local wall-clock times.
export function calendarEventUrl({
  title,
  start = null,
  allDay = false,
  minutes = 60,
  details = "",
}) {
  const params = [`action=TEMPLATE`, `text=${encode(title || "New event")}`];
  if (start) {
    const end = allDay
      ? addDays(startOfDay(start), 1)
      : new Date(start.getTime() + minutes * 60000);
    params.push(`dates=${stamp(start, !allDay)}/${stamp(end, !allDay)}`);
  }
  if (details) params.push(`details=${encode(details)}`);
  return `https://calendar.google.com/calendar/render?${params.join("&")}`;
}

export const MAIL_BODY_LIMIT = 1800;

// A compose window with the draft filled in. Nothing is sent until the user presses Send.
export function mailComposeUrl(account, { to = "", subject = "", body = "" }) {
  const text = String(body || "").slice(0, MAIL_BODY_LIMIT);
  const recipient = /^[^\s@,;]+@[^\s@,;]+\.[^\s@,;]+$/.test(String(to).trim())
    ? String(to).trim()
    : "";
  if (account === "outlook" || account === "hotmail") {
    return `https://outlook.live.com/mail/0/deeplink/compose?to=${encode(recipient)}&subject=${encode(subject)}&body=${encode(text)}`;
  }
  return `https://mail.google.com/mail/?view=cm&fs=1&to=${encode(recipient)}&su=${encode(subject)}&body=${encode(text)}`;
}

const QUICK_LINKS = [
  [
    /^(?:create|make|start|open|new)\s+(?:a\s+|an\s+)?(?:new\s+)?(?:blank\s+)?(?:google\s+)?(?:doc|document)$/i,
    "https://docs.new",
    "a new Google Doc",
  ],
  [
    /^(?:create|make|start|open|new)\s+(?:a\s+|an\s+)?(?:new\s+)?(?:blank\s+)?(?:google\s+)?(?:sheet|spreadsheet)$/i,
    "https://sheets.new",
    "a new Google Sheet",
  ],
  [
    /^(?:create|make|start|open|new)\s+(?:a\s+|an\s+)?(?:new\s+)?(?:blank\s+)?(?:google\s+)?(?:slides?|presentation|slide deck)$/i,
    "https://slides.new",
    "a new Google Slides deck",
  ],
  [
    /^(?:create|make|start|open|new)\s+(?:a\s+|an\s+)?(?:new\s+)?(?:google\s+)?(?:form)$/i,
    "https://forms.new",
    "a new Google Form",
  ],
  [
    /^(?:start|create|open|new|begin)\s+(?:a\s+|an\s+)?(?:new\s+)?(?:google\s+)?meet(?:ing)?(?:\s+(?:call|link|room))?$/i,
    "https://meet.google.com/new",
    "a new Google Meet room",
  ],
  [
    /^(?:create|make|add|new|open)\s+(?:a\s+|an\s+)?(?:new\s+)?(?:google\s+)?keep\s+note$/i,
    "https://keep.new",
    "a new Google Keep note",
  ],
];

// ------------------------------------------------------------------- the parser
const TIME_RE =
  /^(?:what(?:['’]?s| is)|tell me|say|give me|do you (?:know|have))\s+the\s+(?:current\s+)?time(?:\s+(?:is it|it is|right now|now))*$|^what time is it(?:\s+(?:right now|now))?$|^(?:the\s+)?(?:current\s+)?time\s+(?:right now|now)$|^(?:the\s+)?current time$|^(?:abhi\s+)?(?:time|samay) kya (?:hai|hua|ho raha)(?: hai)?$|^kitne baje(?: hain| hai)?$/i;
const DATE_RE =
  /^(?:(?:what(?:['’]?s| is)?|tell me|say)\s+)?(?:the\s+|today['’]?s\s+)?(?:date|day)(?:\s+(?:is it|it is|today|is it today|is today))*$|^what day is it(?:\s+today)?$|^(?:what(?:['’]?s| is)\s+)?today['’]?s date$|^aaj (?:kya|kaun ?sa) (?:tarikh|taareekh|din|date) hai$/i;

const TIMER_RES = [
  /^(?:(?:set|start|put|create|make|begin|run|add)\s+)?(?:an?\s+|the\s+)?(?:timer|countdown)\s+(?:for|of|to)\s+(.+)$/i,
  /^(?:(?:set|start|put|create|make|begin|run|add)\s+)?(?:an?\s+|the\s+)?(.+?)[\s-]+(?:timer|countdown)$/i,
  /^(?:timer|countdown)\s+(.+)$/i,
];
const ALARM_RES = [
  /^(?:(?:set|create|put|make|add|keep|schedule)\s+)?(?:an?\s+|the\s+|my\s+)?alarm\s+(?:for|at|to|of)\s+(.+)$/i,
  /^(?:(?:set|create|put|make|add|keep|schedule)\s+)?(?:an?\s+|the\s+|my\s+)?(.+?)\s+alarm$/i,
  /^wake me(?: up)?\s+(.+)$/i,
  /^alarm\s+(.+)$/i,
];
const REMIND_RE =
  /^(?:remind me|set a reminder|create a reminder|add a reminder|make a reminder|remember to remind me)\b\s*(.*)$/i;
const ALARM_LIST_RE =
  /^(?:(?:what|which|show|list|tell me|read|do i have|any|are there|check)\b.{0,30})?\b(?:alarms?|timers?|reminders?)\b(?:\s+(?:do i have|are set|have i set|did i set|are there|set|running|pending|left|i have|for today|today))*$|^how (?:much|long)\b.{0,30}\b(?:timer|countdown|alarm)\b.{0,20}$|^how much time (?:is |do i have )?(?:left|remaining)$/i;
const ALARM_CANCEL_RE =
  /^(?:cancel|delete|remove|stop|clear|turn off|switch off|dismiss|forget)\s+(all\s+|every\s+)?(?:the\s+|my\s+|of my\s+|of the\s+)?(alarms?|timers?|reminders?|countdowns?)(?:\s+(?:for|at|about|to|called|named)\s+(.+))?$/i;

const NEWS_PLAIN_RE =
  /^(?:(?:tell me|give me|read(?: me| out)?|what(?:['’]?s| is| are)|show me|get me|any|i want(?: to hear)?)\s+)?(?:the\s+|today['’]?s\s+|latest\s+|top\s+|some\s+|breaking\s+|current\s+|main\s+)*(?:news|headlines)(?:\s+(?:today|now|right now|for today|of today|of the day|update|updates|please))*$/i;
const NEWS_TOPIC_RE =
  /^(?:(?:tell me|give me|read(?: me| out)?|what(?:['’]?s| is| are)|show me|get me|any|i want(?: to hear)?)\s+)?(?:the\s+|today['’]?s\s+|latest\s+|top\s+|some\s+|breaking\s+|current\s+)*(?:news|headlines)\s+(?:about|on|of|for|regarding|in|from|related to)\s+(.+)$/i;
const NEWS_PREFIX_RE =
  /^(?:(?:tell me|give me|read(?: me| out)?|what(?:['’]?s| is| are)|show me|get me|any)\s+)?(?:the\s+|today['’]?s\s+|latest\s+|top\s+|some\s+)*(.+?)\s+(?:news|headlines)(?:\s+(?:today|now|please))*$/i;
const NEWS_WORLD_RE =
  /^(?:what(?:['’]?s| is)\s+(?:happening|going on|new)|what(?:['’]?s| is) up)\s+(?:in|around|with)\s+(?:the\s+)?(world|india|country)(?:\s+(?:today|now|right now))?$/i;
const NEWS_NOT_TOPIC_RE =
  /^(?:open|launch|visit|go to|start|google|bbc|ndtv|cnn|my|any|good|bad|big|great|no|fake|this|that|your|more|other|old)\b/i;

const MAPS_RES = [
  /^(?:find|show|locate|search(?: for)?|look up|look for|open|see|get|pull up)\s+(?:me\s+)?(?:this place\s*[:,-]?\s*)?(.+?)\s+(?:on|in|at)\s+(?:the\s+|a\s+|google\s+)?maps?$/i,
  /^(?:find|show|locate|search(?: for)?)\s+(?:me\s+)?this place on\s+(?:the\s+|a\s+|google\s+)?maps?\s*[:,-]?\s*(.+)$/i,
  /^(?:open\s+)?(?:google\s+)?maps?\s+(?:and\s+)?(?:find|show|search(?: for)?|locate|look for|look up)\s+(?:me\s+)?(.+)$/i,
  /^(?:show me\s+)?(?:a\s+|the\s+)?map of\s+(.+)$/i,
  /^where is\s+(.+?)\s+(?:on|in)\s+(?:the\s+|google\s+)?maps?$/i,
];
const DIRECTIONS_RES = [
  /^(?:(?:get|give|show|find)\s+(?:me\s+)?)?(?:the\s+)?(?:directions?|route|navigation|way)\s+(?:to|for)\s+(.+?)(?:\s+from\s+(.+))?$/i,
  /^navigate\s+(?:me\s+)?to\s+(.+?)(?:\s+from\s+(.+))?$/i,
  /^how (?:do|can|should) i (?:get|go|reach|drive)(?:\s+to)?\s+(.+?)(?:\s+from\s+(.+))?$/i,
  /^(?:directions?|route)\s+from\s+(.+?)\s+to\s+(.+)$/i,
];

const SPOTIFY_RES = [
  /^(?:play|put on|start playing|listen to)\s+(.+?)\s+(?:on|in|from|using|with|via)\s+spotify$/i,
  /^(?:on\s+)?spotify[,:]?\s+(?:play|put on)\s+(.+)$/i,
  /^(?:open|launch|start)\s+spotify\s+(?:and|then|,)\s*(?:play|put on|search(?: for)?|find)\s+(.+)$/i,
  /^(?:search|find|look for|look up)\s+(?:for\s+)?(.+?)\s+(?:on|in)\s+spotify$/i,
  /^(?:search|find)\s+spotify\s+for\s+(.+)$/i,
];
const YOUTUBE_SEARCH_RES = [
  /^(?:search|find|look for|look up|show me)\s+(?:for\s+)?(.+?)\s+(?:on|in)\s+youtube$/i,
  /^(?:search|find)\s+youtube\s+for\s+(.+)$/i,
  /^(?:open\s+)?youtube\s+(?:and\s+)?(?:search|find|look for)\s+(?:for\s+)?(.+)$/i,
];
const SONG_WORDS_RE =
  /^(?:the\s+|a\s+|an\s+)?(?:song|track|music|album|playlist|video)\s+(?:called\s+|named\s+|of\s+)?|\s+(?:song|track|music|video)$/gi;

const EVENT_RE =
  /^(?:add|create|schedule|put|book|set up|setup|make|plan|arrange|fix)\s+(.*\b(?:calendar|event|meeting|appointment)\b.*)$/i;
const EVENT_SOFT_RE = /^(?:schedule|arrange|set up|setup)\s+(.+)$/i;
const CALENDAR_VIEW_RE =
  /^(?:what(?:['’]?s| is| do i have)|show(?: me)?|check|see|view)\s+(?:on\s+)?(?:my\s+|the\s+)?(?:google\s+)?(?:calendar|schedule|agenda)(?:\s+(?:for\s+|on\s+)?(today|tomorrow|this week|the week))?$|^(?:what do i have|what(?:['’]?s| is) planned)\s+(?:for\s+|on\s+)?(today|tomorrow|this week)$/i;
const CONNECT_CHAT_RE =
  /^(?:connect|link|sign in to|sign into|log in to|log into|login to|set up|setup)\s+(?:to\s+)?(?:my\s+)?(whatsapp|telegram)(?:\s+(?:web|account))?$/i;
const EVENT_NOISE_RE =
  /\b(?:(?:to|on|in|into)\s+(?:my\s+|the\s+)?(?:google\s+)?calendar|(?:a\s+|an\s+|the\s+|new\s+)*(?:google\s+)?calendar\s+(?:event|entry)|(?:a\s+|an\s+|the\s+|new\s+)+(?:event|entry)(?!\s+management)|called|named|titled|for me)\b/gi;

const DRIVE_RES = [
  /^(?:search|find|look for|look up)\s+(?:for\s+)?(.+?)\s+(?:in|on|from)\s+(?:my\s+|the\s+)?(?:google\s+)?drive$/i,
  /^(?:search|look in)\s+(?:my\s+|the\s+)?(?:google\s+)?drive\s+for\s+(.+)$/i,
];
const MAIL_SEARCH_RES = [
  /^(?:search|find|look for|look up|show)\s+(?:for\s+)?(?:(?:e-?mails?|mails?)\s+(?:from|about|regarding|with)\s+)?(.+?)\s+(?:in|on)\s+(?:my\s+|the\s+)?(?:gmail|g-?mail|inbox|mailbox|e-?mails?|mails?)$/i,
  /^(?:search|look in)\s+(?:my\s+|the\s+)?(?:gmail|inbox|mailbox|e-?mails?|mails?)\s+for\s+(.+)$/i,
  /^(?:find|show|search(?: for)?)\s+(?:me\s+)?(?:the\s+|my\s+)?(?:e-?mails?|mails?)\s+(?:from|about|regarding)\s+(.+)$/i,
];

const MAIL_RES = [
  /^(?:write|compose|draft|send|prepare|type|create|make)\s+(?:an?\s+|the\s+|one\s+)?(?:new\s+)?(?:e-?mail|mail)\s+(?:to|for)\s+(.+?)\s+(about|regarding|saying|that says|which says|stating|telling|to say|to tell|to ask|to inform|to request|asking|informing|requesting|on|that|for)\s+(.+)$/i,
  /^(?:e-?mail|mail)\s+(?:to\s+)?(.+?)\s+(about|regarding|saying|that says|stating|to say|to tell|to ask|asking|informing|requesting|that)\s+(.+)$/i,
  /^(?:write|compose|draft|send|prepare|type|create|make)\s+(?:an?\s+|the\s+|one\s+)?(?:new\s+)?(?:e-?mail|mail)\s+(about|regarding|saying|that says|stating|to say|asking|informing|requesting|on)\s+(.+?)\s+(?:to|for)\s+(\S+@\S+)$/i,
];
const MAIL_ACCOUNT_RE =
  /\s+(?:from|using|with|via|through|in|on)\s+(?:my\s+)?(hotmail|outlook|gmail|g-?mail|google mail)(?:\s+(?:account|id|address|mail))?$/i;

const SCREEN_ON_RE =
  /^(?:(?:start\s+)?(?:watch|watching|look at|looking at|see|share|sharing|read|monitor)\s+(?:my\s+|the\s+|this\s+)?screen|screen\s?share|share screen|turn on screen (?:watch|share|sharing))$/i;
const SCREEN_OFF_RE =
  /^(?:stop|end|quit|turn off|disable)\s+(?:watching\s+|looking at\s+|sharing\s+|the\s+)?(?:my\s+|the\s+)?screen(?:\s?(?:watch|share|sharing))?$/i;
// A question about what is on the screen. An order to do something else ("send…",
// "search…", "play…", "write…") never counts, whatever words it contains.
const SCREEN_ORDER_RE =
  /^(?:send|message|text|dm|reply|post|search|google|look up|browse|play|open|comment|subscribe|call|set|remind|start|launch|write|create|make|build|generate|draft|compose|e-?mail|mail)\b/i;
const SCREEN_NAMED_RE =
  /\b(?:on|at|in) (?:my|the|this) (?:screen|display|monitor)\b|\b(?:see|read|check|describe|explain) (?:my|the|this) (?:screen|display|monitor)\b/i;
const SCREEN_POINTING_RE =
  /\bthis (?:page|error|window|code|chart|image|picture|photo|email|e-mail|mail|message|document|doc|tab|site|website|video|line|form|table|graph|app|file|text|article|slide|screen|paragraph|sentence|word|button|setting|popup|pop-up|dialog|warning|notification)\b|\b(?:what|who|where|which)(?:['’]?s| is| are) (?:this|that|these|those)\b|\bwhat am i (?:looking at|seeing|watching|reading)\b|\b(?:can|do) you see\b|\bwhat (?:do|can) you see\b|\b(?:look at|see|read|explain|translate|summari[sz]e|solve|fix|check|describe) (?:this|that|it|these|those)\b|\bwhat does (?:this|that|it) (?:say|mean|do|show)\b|\b(?:written|shown|displayed|happening|going on|wrong) here\b|\bin front of me\b/i;
const MINI_ON_RE =
  /^(?:show|open|start|enable|turn on|pop out|bring up)\s+(?:the\s+|a\s+|your\s+)?(?:mini|small|little|tiny|floating)\s+orb$|^(?:mini|floating) orb$|^float(?: the orb)?$|^pop out$/i;
const MINI_OFF_RE =
  /^(?:hide|close|stop|disable|turn off|remove)\s+(?:the\s+|your\s+)?(?:mini|small|little|tiny|floating)\s+orb$/i;

function firstMatch(patterns, value) {
  for (const pattern of patterns) {
    const match = value.match(pattern);
    if (match) return match;
  }
  return null;
}

function tidy(value) {
  return String(value || "")
    .replace(/^[\s"'“”‘’:,-]+|[\s"'“”‘’:,.-]+$/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function parseTimer(value) {
  if (
    /^(?:set|start|put|create|make|begin|run|add)\s+(?:an?\s+|the\s+)?(?:timer|countdown)$/i.test(
      value,
    )
  ) {
    return { kind: "say", text: "For how long? Say for example “set a timer for 10 minutes”." };
  }
  const match = firstMatch(TIMER_RES, value);
  if (!match) return null;
  let body = match[1].trim();
  let label = "";
  const named = body.match(/^(.+?)\s+(?:called|named|for)\s+(.+)$/i);
  if (named && parseDuration(named[1])) {
    body = named[1];
    label = tidy(named[2]);
  }
  const ms = /^\d{1,3}$/.test(body) ? Number(body) * 60000 : parseDuration(body);
  if (!ms) return null;
  if (ms > 24 * 3600000)
    return {
      kind: "say",
      text: "A timer can run for up to 24 hours. For anything later, set an alarm or a reminder.",
    };
  return { kind: "timer", ms, label };
}

function parseAlarm(value, now) {
  const match = firstMatch(ALARM_RES, value);
  if (!match) return null;
  const when = parseWhen(match[1], now, { bareTime: true });
  if (!when || !when.hasTime) {
    if (/^wake me/i.test(value) || /\balarm\b/i.test(value)) {
      return {
        kind: "say",
        text: "What time should the alarm ring? Say for example “set an alarm for 6:30 am”.",
      };
    }
    return null;
  }
  const label = tidy(
    when.rest
      .replace(/^(?:for|at|to|by|on)\b/i, "")
      .replace(/\b(?:called|named|labelled|labeled|to|for|at|by)\s*$/i, "")
      .replace(/^(?:called|named|labelled|labeled)\s+/i, ""),
  );
  return {
    kind: "alarm",
    at: when.at.getTime(),
    repeat: when.repeat,
    label: /^(?:up|me|an?|the)?$/i.test(label) ? "" : label,
  };
}

function parseReminder(value, now) {
  const match = value.match(REMIND_RE);
  if (!match) return null;
  const body = match[1].trim();
  const when = parseWhen(body, now);
  const ask = {
    kind: "say",
    text: "When should I remind you? Say for example “remind me to call mom at 5 pm” or “remind me in 20 minutes to drink water”.",
  };
  if (!body) return ask;
  if (!when) return ask;
  const label = tidy(
    when.rest
      .replace(/^(?:to|about|that|of|for)\s+/i, "")
      .replace(/\s+(?:at|on|in|by|to|about|that)$/i, "")
      .replace(/^(?:to|about|that|of|for)\s+/i, ""),
  );
  if (!label)
    return {
      kind: "say",
      text: "What should I remind you about? Say for example “remind me to call mom at 5 pm”.",
    };
  return { kind: "reminder", at: when.at.getTime(), repeat: when.repeat, label };
}

function parseEvent(value, now) {
  let match = value.match(EVENT_RE);
  let when = match ? parseWhen(match[1], now) : null;
  if (!match) {
    // "schedule lunch with mom tomorrow at 1 pm": an event only when a day or time is named.
    match = value.match(EVENT_SOFT_RE);
    when = match ? parseWhen(match[1], now) : null;
    if (
      !match ||
      !when ||
      /\b(?:post|tweet|message|e-?mail|mail|whatsapp|telegram|instagram|video|upload|scan|backup|task|job|script)\b/i.test(
        match[1],
      )
    )
      return null;
  }
  const text = when ? when.rest : match[1];
  let title = tidy(
    text
      .replace(EVENT_NOISE_RE, " ")
      .replace(/\s+/g, " ")
      .replace(/^(?:a|an|the|my|new)\s+/i, "")
      .replace(/\s+(?:on|at|for|to|in|by|from)$/i, ""),
  );
  title = title.replace(/^(?:calendar\s+)?(?:event|entry)\s+(?=\S)/i, "");
  title = title.replace(/^(?:for|about|with)\s+(?=\S)/i, (word) =>
    /^with/i.test(word) ? "Meeting with " : "",
  );
  if (!title || /^(?:calendar|event|entry)$/i.test(title)) title = "New event";
  title = title.replace(/^./, (letter) => letter.toUpperCase());
  return {
    kind: "event",
    title,
    start: when ? when.at.getTime() : null,
    allDay: Boolean(when && !when.hasTime),
    url: calendarEventUrl({
      title,
      start: when ? when.at : null,
      allDay: Boolean(when && !when.hasTime),
    }),
  };
}

function parseMail(value) {
  let text = value;
  let account = "";
  const named = text.match(MAIL_ACCOUNT_RE);
  if (named) {
    account = /hotmail|outlook/i.test(named[1]) ? "outlook" : "gmail";
    text = text.slice(0, named.index).trim();
  }
  let match = text.match(MAIL_RES[0]) || text.match(MAIL_RES[1]);
  if (match) {
    const to = tidy(match[1]).replace(/^(?:my|the)\s+/i, "");
    const about = tidy(match[3]);
    if (!to || !about) return null;
    return {
      kind: "mail",
      to,
      about,
      account,
      mode: /^(?:about|regarding|on|for)$/i.test(match[2]) ? "topic" : "message",
    };
  }
  match = text.match(MAIL_RES[2]);
  if (match)
    return { kind: "mail", to: tidy(match[3]), about: tidy(match[2]), account, mode: "topic" };
  return null;
}

function parseNews(value) {
  if (NEWS_PLAIN_RE.test(value)) return { kind: "news", topic: "" };
  let match = value.match(NEWS_TOPIC_RE);
  if (match)
    return {
      kind: "news",
      topic: tidy(match[1])
        .replace(/^the\s+/i, "")
        .slice(0, 80),
    };
  match = value.match(NEWS_WORLD_RE);
  if (match) return { kind: "news", topic: /world/i.test(match[1]) ? "world" : "India" };
  match = value.match(NEWS_PREFIX_RE);
  if (match) {
    const topic = tidy(match[1]);
    if (
      topic &&
      topic.split(" ").length <= 4 &&
      !NEWS_NOT_TOPIC_RE.test(topic) &&
      !/\b(?:is|are|was|were|the|about|of)\b/i.test(topic)
    ) {
      return { kind: "news", topic: topic.slice(0, 80) };
    }
  }
  return null;
}

// What the sentence asks for, or null when it is not one of these commands and
// should go on to the rest of the app (sites, browser tasks, the cloud brain).
export function parseInstantCommand(text, now = new Date()) {
  const value = cleanCommand(text);
  if (!value || value.length > 300) return null;

  if (TIME_RE.test(value)) return { kind: "time" };
  if (DATE_RE.test(value)) return { kind: "date" };

  const cancel = value.match(ALARM_CANCEL_RE);
  if (cancel) {
    const what = cancel[2].toLowerCase().replace(/s$/, "").replace("countdown", "timer");
    return {
      kind: "alarm-cancel",
      what,
      all: Boolean(cancel[1]) || /s$/i.test(cancel[2]),
      which: tidy(cancel[3] || ""),
    };
  }
  if (ALARM_LIST_RE.test(value) && !/^(?:set|create|add|make|start)\b/i.test(value))
    return { kind: "alarm-list" };
  const reminder = parseReminder(value, now);
  if (reminder) return reminder;
  const timer = parseTimer(value);
  if (timer) return timer;
  const alarm = parseAlarm(value, now);
  if (alarm) return alarm;

  const news = parseNews(value);
  if (news) return news;

  let match = firstMatch(DIRECTIONS_RES, value);
  if (match) {
    const reversed = /^(?:directions?|route)\s+from\b/i.test(value);
    const destination = tidy(reversed ? match[2] : match[1]);
    const origin = tidy(reversed ? match[1] : match[2] || "");
    if (destination)
      return {
        kind: "link",
        url: mapsDirectionsUrl(destination, origin),
        label: `directions to ${destination}`,
        where: "maps",
        own: false,
      };
  }
  match = firstMatch(MAPS_RES, value);
  if (match) {
    const place = tidy(match[1]).replace(
      /^(?:the\s+)?(?:place|location|address)\s+(?:called\s+|named\s+|of\s+)?/i,
      "",
    );
    if (place && !/^(?:it|this|that|here|there)$/i.test(place)) {
      return {
        kind: "link",
        url: mapsSearchUrl(place),
        label: `“${place}” on Google Maps`,
        where: "maps",
        own: false,
      };
    }
  }

  match = firstMatch(SPOTIFY_RES, value);
  if (match) {
    const query = tidy(match[1].replace(SONG_WORDS_RE, " "));
    if (query) return { kind: "music", service: "spotify", query, url: spotifySearchUrl(query) };
  }
  match = firstMatch(YOUTUBE_SEARCH_RES, value);
  if (match) {
    const query = tidy(match[1]);
    if (query)
      return {
        kind: "link",
        url: youtubeSearchUrl(query),
        label: `YouTube results for “${query}”`,
        where: "youtube",
        own: false,
      };
  }

  const mail = parseMail(value);
  if (mail) return mail;
  const event = parseEvent(value, now);
  if (event) return event;

  for (const [pattern, url, label] of QUICK_LINKS) {
    if (pattern.test(value)) return { kind: "link", url, label, where: "google", own: true };
  }
  match = firstMatch(DRIVE_RES, value);
  if (match && tidy(match[1])) {
    const query = tidy(match[1]);
    return {
      kind: "link",
      url: `https://drive.google.com/drive/search?q=${encode(query)}`,
      label: `“${query}” in Google Drive`,
      where: "google",
      own: true,
    };
  }
  match = firstMatch(MAIL_SEARCH_RES, value);
  if (match && tidy(match[1])) {
    const query = tidy(match[1]);
    return {
      kind: "link",
      url: `https://mail.google.com/mail/u/0/#search/${encode(query)}`,
      label: `mail matching “${query}” in Gmail`,
      where: "google",
      own: true,
    };
  }

  match = value.match(CALENDAR_VIEW_RE);
  if (match) {
    const span = (match[1] || match[2] || "today").toLowerCase();
    const day = new Date(
      now.getFullYear(),
      now.getMonth(),
      now.getDate() + (span === "tomorrow" ? 1 : 0),
    );
    const view = /week/.test(span) ? "week" : "day";
    return {
      kind: "link",
      url: `https://calendar.google.com/calendar/r/${view}/${day.getFullYear()}/${day.getMonth() + 1}/${day.getDate()}`,
      label: `your Google Calendar for ${/week/.test(span) ? "this week" : span}`,
      where: "google",
      own: true,
      note: "I can show it, but I cannot read your events out from here.",
    };
  }
  match = value.match(CONNECT_CHAT_RE);
  if (match) return { kind: "open", targets: [{ name: match[1].toLowerCase(), kind: "auto" }] };

  if (SCREEN_ON_RE.test(value)) return { kind: "screen", on: true };
  if (SCREEN_OFF_RE.test(value)) return { kind: "screen", on: false };
  if (MINI_ON_RE.test(value)) return { kind: "mini", on: true };
  if (MINI_OFF_RE.test(value)) return { kind: "mini", on: false };

  const refused = parseCall(value) || parseHomeDevice(value);
  if (refused) return refused;

  return parseOpen(value);
}

// ------------------------------------------------------------------------ mail
// The request sent to the cloud brain for "write an email to … about …". The brain
// writes the words; nothing is sent until the user presses Send in the mail window.
// ------------------------------------------------- said plainly: not possible here
// A language model that is asked to "call mom" or "turn on the AC" may answer as if it
// had done it. These sentences are answered here instead, at once, with what is true.
// The rules are narrow on purpose: a sentence they do not recognise goes on to the
// brain as before, so "call center jobs in Noida" or "open Jio TV" stay ordinary requests.
const CALL_VIA = "(?:whats\\s?app|telegram|instagram|insta|phone|mobile|video|voice|audio)";
const CALL_ON = `(?:\\s+(?:on|via|using|through|over)\\s+(?:the\\s+|my\\s+)?${CALL_VIA}(?:\\s+call)?)?`;
const CALL_TAIL = "(?:\\s+(?:now|right now|right away|once|again|back))?";
const CALL_DO = "(?:karo|kar do|kardo|kar|lagao|laga do|lagado|milao|mila do|kijiye)";
const CALL_PLACE_RES = [
  `^(?:make|place|start|do|give)\\s+(?:a\\s+|an\\s+)?(?:${CALL_VIA}\\s+)*call(?:\\s+(?:to|with)\\s+(.+?))?${CALL_ON}${CALL_TAIL}$`,
  `^give\\s+(.+?)\\s+a\\s+(?:${CALL_VIA}\\s+)?(?:call|ring)${CALL_ON}${CALL_TAIL}$`,
  `^(?:${CALL_VIA}\\s+)?(?:call|dial)\\s+(?:to\\s+)?(?!(?:me|it|this|that|off|out|back|in|up|on|down|of|for|by|from|about|at|with|and|or|is|was)\\b)(.+?)${CALL_ON}${CALL_TAIL}$`,
  `^(.+?)\\s+ko\\s+(?:${CALL_VIA}\\s+)?(?:call|phone|fone)\\s+${CALL_DO}$`,
  `^(?:call|phone|fone)\\s+${CALL_DO}\\s+(.+?)\\s+ko$`,
].map((source) => new RegExp(source, "i"));
const CALL_ANSWER_RE =
  /^(?:answer|pick up|pickup|accept|receive|attend|take|reject|decline|cut|end|hang up|disconnect)\s+(?:the\s+|this\s+|that\s+|my\s+|an?\s+|incoming\s+|whatsapp\s+|telegram\s+|instagram\s+|phone\s+|video\s+|voice\s+)*(?:calls?|phone)(?:\s+from\s+.{1,40})?$|^(?:call|phone)\s+(?:uthao|utha lo|uthalo|utha do|receive karo|kaat do|kat do)$/i;
const EMERGENCY_CALL_RE =
  /^(?:call|dial|phone|ring)\s+(?:for\s+|to\s+)?(?:the\s+|an?\s+)?(?:ambulance|police|fire brigade|fire station|fire department|fire service|emergency|emergency services?|help|100|101|102|108|112|911|999)\b/i;
// Things that are called without a telephone: "call the API", "call a meeting".
const NOT_A_PERSON_RE =
  /\b(?:functions?|methods?|apis?|endpoints?|scripts?|code|commands?|class|url|service|number of|meeting|day|bluff|shots?|attention|question|cent(?:er|re)s?|recording|history|logs?|options?|waiting|forwarding|rates?|duty|tone|pad|quality|drops?|sheet)\b/i;
const CALL_WHY =
  "I work through the chat pages in a browser window, where I read and type text, so I have no way to speak or listen inside a call.";

function parseCall(value) {
  if (EMERGENCY_CALL_RE.test(value)) {
    return {
      kind: "say",
      text: "I can't place calls, so please dial it yourself right now. The emergency number in India is 112. Nothing was dialled.",
    };
  }
  if (CALL_ANSWER_RE.test(value)) {
    return {
      kind: "say",
      text: `I can't answer, reject or end calls. ${CALL_WHY} Nothing was answered.`,
    };
  }
  const match = firstMatch(CALL_PLACE_RES, value);
  if (!match) return null;
  const named = tidy(match[1] || "");
  const who = named.replace(/^(?:the|my|our|an?)\s+/i, "");
  if (who.split(" ").length > 3 || NOT_A_PERSON_RE.test(who)) return null;
  // "call a cab" names no contact, and a bare number is not a chat to write to.
  const contact = who && !/^an?\s/i.test(named) && !/^[\d\s+()-]+$/.test(who);
  const offer = contact
    ? ` I can write to ${who} instead: say “send a WhatsApp message to ${who} saying …”.`
    : "";
  return { kind: "say", text: `I can't place calls. ${CALL_WHY}${offer} Nothing was dialled.` };
}

const HOME_DEVICE =
  "(?:a\\.?c\\.?|a\\/c|air[ -]?con|air[ -]?conditioner|air[ -]?conditioning|cooler|heater|geyser|fans?|pankha|pankhe|lights?|batti|lamps?|bulbs?|tube ?lights?|smart plug|air purifier|purifier|thermostat|heating)";
const HOME_SCREEN = "(?:tv|television)";
const HOME_ROOM =
  "(?:bedroom|master bedroom|living room|drawing room|dining room|guest room|kids room|hall|kitchen|bathroom|balcony|study|office|lobby|room)";
// Up to two words may describe the device ("living room light", "ceiling fan"), but not
// little words of the sentence itself ("is the ac on"). A TV takes only a room, because
// "Jio TV" and "YouTube TV" are things to open, not to switch.
const HOME_NOT_A_NAME =
  "(?:is|are|was|the|my|our|an?|being|can|could|will|would|you|please|do|does|did|it|if|when|and|or|to|of|in|on|at|for|with|not|no|turn|switch|set|put|make)";
const HOME_ITEM = `(?:(?:(?!${HOME_NOT_A_NAME}\\b)[\\p{L}']+\\s+){0,2}${HOME_DEVICE}|(?:${HOME_ROOM}\\s+)?${HOME_SCREEN})`;
const HOME_THE = "(?:(?:the|my|our|this|that)\\s+)?";
const HOME_PHRASE = `${HOME_THE}(${HOME_ITEM})`;
// "… and the fan": more devices in the same breath.
const HOME_MORE = `(?:\\s*(?:,|and|aur)\\s+${HOME_THE}${HOME_ITEM})*`;
const HOME_DOING = "(?:karo|kar do|kardo|kar|do|de|dijiye|kijiye|kar dijiye|rakho|rakh do)";
const HOME_DEGREES = "\\d{1,2}(?:\\.\\d)?\\s*(?:°\\s*c?|degrees?(?:\\s+celsius)?|deg|c)?";
const HOME_RES = [
  `^(?:turn|switch|put|power|flip)\\s+(?:on|off)\\s+${HOME_PHRASE}${HOME_MORE}$`,
  `^(?:turn|switch|put|power|flip)\\s+${HOME_PHRASE}${HOME_MORE}\\s+(?:on|off)$`,
  `^(?:on|off|open|close|start|stop|shut|shut off|shut down)\\s+${HOME_PHRASE}${HOME_MORE}$`,
  `^${HOME_PHRASE}${HOME_MORE}\\s+(?:ko\\s+)?(?:on|off|chalu|chala|chalao|jala|jalao|band|bandh|bujha|bujhao|start|stop)(?:\\s+${HOME_DOING})?$`,
  `^(?:set|change|make|keep|put|adjust|turn)\\s+${HOME_PHRASE}\\s+(?:temperature\\s+|temp\\s+)?(?:(?:to|at|on|pe|par)\\s+)?${HOME_DEGREES}$`,
  `^(?:set|change|make|keep|put|adjust)\\s+(?:the\\s+)?(?:temperature|temp)\\s+(?:of\\s+)?${HOME_PHRASE}\\s+(?:to|at)\\s+${HOME_DEGREES}$`,
  `^${HOME_PHRASE}\\s+(?:ko\\s+)?\\d{1,2}\\s*(?:pe|par|degrees?|deg)(?:\\s+(?:${HOME_DOING}|set karo))?$`,
  `^(?:set|change|put|switch)\\s+${HOME_PHRASE}\\s+(?:to|on|in|into)\\s+(?:cool|cooling|heat|heating|dry|fan|auto|sleep|turbo|eco)(?:\\s+mode)?$`,
  `^(?:increase|decrease|raise|lower|reduce|dim|brighten)\\s+${HOME_PHRASE}(?:\\s+(?:temperature|temp|speed|brightness))?(?:\\s+(?:by|to)\\s+\\d{1,3}\\s*(?:%|degrees?)?)?$`,
  `^(?:increase|decrease|raise|lower|reduce|set|change)\\s+(?:the\\s+)?(?:temperature|temp|speed|brightness)\\s+of\\s+${HOME_PHRASE}(?:\\s+(?:by|to)\\s+\\d{1,3}\\s*(?:%|degrees?)?)?$`,
].map((source) => new RegExp(source, "iu"));
const HOME_STATE_RE = new RegExp(
  `^(?:is|are)\\s+${HOME_PHRASE}\\s+(?:still\\s+)?(?:on|off|running|working)$`,
  "iu",
);
const HOME_NAMES = { ac: "AC", "a.c": "AC", "a.c.": "AC", "a/c": "AC", tv: "TV" };
const HOME_REMOTE_RE =
  /\b(?:a\.?c\.?|a\/c|air[ -]?con(?:ditioner|ditioning)?|tv|television)(?![\p{L}\d])/iu;

function parseHomeDevice(value) {
  const asked = value.match(HOME_STATE_RE);
  const match = asked || firstMatch(HOME_RES, value);
  if (!match) return null;
  const several = /,|\b(?:and|aur)\b/i.test(value);
  const device = several
    ? ""
    : tidy(match[1])
        .split(" ")
        .map((word) => HOME_NAMES[word.toLowerCase()] || word)
        .join(" ");
  if (asked) {
    const verb = /s$/i.test(device) && !/(?:AC|TV)$/.test(device) ? "are" : "is";
    return {
      kind: "say",
      text: `I can't see whether the ${device} ${verb} on: this app has no connection to home devices.`,
    };
  }
  // Only what is usually driven by an infrared remote gets the hint about the blaster.
  const remote = value.match(HOME_REMOTE_RE);
  const hint = remote
    ? ` ${/^t/i.test(remote[0]) ? "A TV" : "An AC"} that listens only to its infrared remote also needs a Wi-Fi infrared blaster in the room before any program can reach it.`
    : "";
  return {
    kind: "say",
    text: `I can't control ${device ? `the ${device}` : "those"} yet: this app has no connection to home devices.${hint} Nothing was switched.`,
  };
}

// ------------------------------------------------------------- watching chats
// "Watch my WhatsApp chat with Boss" is understood here, so that putting a chat on
// watch needs no cloud planner. Anything more involved returns null and is planned.
const WATCH_LEAD_RE =
  /^(?:watch|monitor|keep (?:an? )?eye on|keep watching|look after|keep track of)\s+(.+)$/i;
const WATCH_APP = "(whats\\s?app|telegram|instagram|insta)";
const WATCH_TAILS = [
  // when to ask
  /[\s,]+(?:and\s+)?(?:(?:ask|tell|alert|notify|ping|inform)\s+me\s+)?(?:immediately|at once|right away|straight away|instantly)$/i,
  /[\s,]+(?:and\s+)?(?:(?:ask|tell|alert|notify|ping|inform)\s+me\s+)?(?:after|in|within)\s+(?:\d{1,3}|an?|one|two|three|five|ten|fifteen|thirty)\s*(?:seconds?|secs?|minutes?|mins?|hours?|hrs?)$/i,
  // who writes the answer
  /[\s,]+(?:and\s+)?(?:you (?:can|could|may) (?:reply|answer|respond)(?: for me)?|(?:reply|answer|respond) for me|suggest (?:a |the )?repl(?:y|ies)|propose (?:a |the )?repl(?:y|ies))$/i,
  // what counts
  /[\s,]+(?:and\s+)?(?:only\s+)?for (?:urgent|important) (?:messages?|things?|stuff)(?: only)?$/i,
  /[\s,]+(?:and\s+)?(?:ask|tell|alert|notify|ping|inform) me(?: (?:when|if) (?:someone|somebody|anyone|he|she|they) (?:messages?|texts?|writes?)(?: me)?)?$/i,
  /[\s,]+(?:when|while|whenever) i(?: am|['’]m) (?:away|busy|out|not (?:here|around|available))$/i,
  /[\s,]+for me$/i,
];
const WATCH_NAME_RE = /^[\p{L}\p{N}][\p{L}\p{N} .'’&()+-]{0,78}$/u;

function watchPlatform(word) {
  const key = String(word || "")
    .toLowerCase()
    .replace(/\s+/g, "");
  if (key === "whatsapp") return "whatsapp";
  if (key === "telegram") return "telegram";
  return "instagram";
}

export function parseWatchRequest(text) {
  const lead = cleanCommand(text).match(WATCH_LEAD_RE);
  if (!lead) return null;
  let core = lead[1].trim();
  for (let pass = 0; pass < 4; pass++) {
    const before = core;
    for (const tail of WATCH_TAILS) core = core.replace(tail, "").trim();
    if (core === before) break;
  }
  const every = core.match(
    new RegExp(
      `^(?:(?:all|every|each|any)\\s+)?(?:of\\s+)?(?:my\\s+|the\\s+)?${WATCH_APP}(?:\\s+(?:chats?|messages?|conversations?|dms?|inbox|account))?$`,
      "i",
    ),
  );
  if (every) return { platform: watchPlatform(every[1]), chat: "", all: true };
  const withName = core.match(
    new RegExp(
      `^(?:my\\s+|the\\s+)?${WATCH_APP}(?:\\s+(?:chats?|messages?|conversations?|dms?|group))?\\s+(?:with|from|of|called|named)\\s+(.+)$`,
      "i",
    ),
  );
  const onApp = core.match(
    new RegExp(
      `^(?:(?:my\\s+)?(?:chats?|conversations?|messages?)\\s+(?:with|from)\\s+)?(.+?)\\s+(?:on|in)\\s+(?:my\\s+)?${WATCH_APP}$`,
      "i",
    ),
  );
  const platform = withName ? withName[1] : onApp ? onApp[2] : "";
  const name = (withName ? withName[2] : onApp ? onApp[1] : "")
    .replace(/^(?:the|my)\s+/i, "")
    .replace(/[“”"]/g, "")
    .trim();
  if (!platform || !WATCH_NAME_RE.test(name)) return null;
  if (/\b(?:and|then|if|when|but|or)\b|,/i.test(name)) return null; // more was said: let it be planned
  return { platform: watchPlatform(platform), chat: name, all: false };
}

// How long a message may wait before Weronika asks about it, in seconds.
export const WATCH_WAIT_SECONDS = 60;
export function watchWaitSeconds(text) {
  const value = String(text || "").toLowerCase();
  if (
    /\b(?:immediately|at once|right away|straight away|instantly|as soon as|the moment)\b/.test(
      value,
    )
  )
    return 0;
  const said =
    value.match(
      /\b(?:after|in|within|every|for)\s+((?:\d{1,3}|an?|one|two|three|five|ten|fifteen|thirty)\s*(?:seconds?|secs?|minutes?|mins?|hours?|hrs?))\b/,
    ) || value.match(/\b(\d{1,3}\s*(?:minutes?|mins?|hours?|hrs?))\b/);
  const ms = said ? parseDuration(said[1]) : null;
  return ms ? Math.min(86400, Math.max(0, Math.round(ms / 1000))) : WATCH_WAIT_SECONDS;
}

// Is this sentence a question about what is on the user's screen? `watching` says
// whether the screen is being shared with Weronika right now: while it is, pointing words
// ("this error", "what is that") are enough; otherwise the screen has to be named.
export function asksAboutScreen(text, watching = false) {
  const value = cleanCommand(text);
  if (!value || SCREEN_ORDER_RE.test(value)) return false;
  if (SCREEN_NAMED_RE.test(value)) return true;
  return Boolean(watching) && SCREEN_POINTING_RE.test(value);
}

export function mailDraftPrompt(command, senderName = "") {
  const ask =
    command.mode === "message"
      ? `Write a short, clear email that tells the reader this: ${command.about}.`
      : `Write a short, clear email about this: ${command.about}.`;
  const from = senderName
    ? ` Sign it as ${senderName}.`
    : " End with a plain sign-off and leave the name out.";
  return [
    `${ask} It is from me to ${command.to}.${from}`,
    "Plain and polite, the way a person writes to a colleague or an acquaintance. No flirting, no endearments, no emoji, no markdown.",
    "Do not invent facts, dates, amounts or names that I did not give. Leave a short [placeholder] where a detail is missing.",
    "Answer in exactly this form and add nothing before or after it:",
    "Subject: <one line>",
    "",
    "<the email text>",
  ].join("\n");
}

export function mailRevisionPrompt(draft, instruction) {
  return [
    "Here is an email draft of mine.",
    `Subject: ${draft.subject}`,
    "",
    draft.body,
    "",
    `Change it like this: ${instruction}`,
    "Keep everything else. Plain and polite, no flirting, no emoji, no markdown. Do not invent facts.",
    "Answer in exactly this form and add nothing before or after it:",
    "Subject: <one line>",
    "",
    "<the email text>",
  ].join("\n");
}

// Splits the brain's answer into subject and text. An answer without a subject line
// is taken as the text alone.
export function parseMailDraft(reply) {
  const text = String(reply || "")
    .replace(/\r/g, "")
    .replace(/^```[a-z]*\n?|\n?```$/gi, "")
    .trim();
  const match = text.match(/^[\s>*_#-]*subject[\s*_]*[:：][\s*_]*(.+)$/im);
  const subject = match
    ? match[1]
        .replace(/[*_`]+/g, "")
        .trim()
        .slice(0, 200)
    : "";
  let body = match
    ? `${text.slice(0, match.index)}\n${text.slice(match.index + match[0].length)}`
    : text;
  body = body
    .replace(/^[\s>*_#-]*(?:body|message|email)[\s*_]*[:：][\s*_]*/im, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
  return { subject, body };
}

// ------------------------------------------------------------------- day plans
const PLAN_DAY_RE =
  /^(?:(?:help me|can you|could you|please)\s+)*(?:plan|organi[sz]e|structure|map out|sort out|schedule)\s+(?:out\s+)?(?:my|the|our)\s+(?:whole\s+|entire\s+)?(day|morning|afternoon|evening|night|week|weekend|tomorrow|today)\b|^what should i do (?:today|tomorrow|this (?:morning|afternoon|evening|weekend))\b|^(?:make|give me|create|suggest)\s+(?:me\s+)?(?:a\s+|my\s+)?(?:plan|schedule|routine|timetable)\s+for\s+(?:my\s+|the\s+)?(day|today|tomorrow|week|weekend|morning|evening)\b/i;

export function isDayPlanRequest(text) {
  return PLAN_DAY_RE.test(cleanCommand(text));
}

// The same request, with what Weronika already knows about the day attached.
export function dayPlanPrompt(text, { now = new Date(), alarms = [] } = {}) {
  const coming = normaliseAlarms(alarms)
    .filter(
      (alarm) =>
        alarm.kind !== "timer" &&
        alarm.at > now.getTime() &&
        alarm.at - now.getTime() < 8 * 86400000,
    )
    .slice(0, 12)
    .map((alarm) => `- ${describeAlarm(alarm, now)}`);
  return [
    String(text || "").trim(),
    "",
    `(For this plan: it is ${formatClock(now)} on ${formatFullDate(now)}.`,
    coming.length
      ? `My alarms and reminders:\n${coming.join("\n")}`
      : "I have no alarms or reminders set.",
    "Build the plan around these and around what you already know about me. Give clock times, keep it realistic, and ask me one question if something important is missing.)",
  ].join("\n");
}

// "Wednesday, 11 November 2026, 3:00 PM (Asia/Kolkata)": sent along with a chat
// message so that answers about today, tomorrow or "how long until" are right.
export function clientTimeLabel(now = new Date(), zone = "") {
  const place = /^[A-Za-z_]+(?:\/[A-Za-z_+-]+){0,2}$/.test(zone) ? ` (${zone})` : "";
  return `${formatFullDate(now)}, ${formatClock(now)}${place}`;
}

// ---------------------------------------------------------------------- alarms
export const ALARM_LIMIT = 40;
const MISSED_AFTER_MS = 120000;

export function normaliseAlarms(raw) {
  if (!Array.isArray(raw)) return [];
  const kinds = new Set(["alarm", "timer", "reminder"]);
  const seen = new Set();
  const list = [];
  for (const entry of raw) {
    if (!entry || typeof entry !== "object") continue;
    const at = Number(entry.at);
    const id = String(entry.id || "").slice(0, 40);
    if (!id || seen.has(id) || !Number.isFinite(at) || at <= 0 || !kinds.has(entry.kind)) continue;
    seen.add(id);
    list.push({
      id,
      kind: entry.kind,
      at,
      label: String(entry.label || "")
        .replace(/\s+/g, " ")
        .trim()
        .slice(0, 160),
      repeat: entry.repeat === "daily" ? "daily" : "",
    });
  }
  return list.sort((a, b) => a.at - b.at).slice(0, ALARM_LIMIT);
}

function nextDaily(at, nowMs) {
  let next = new Date(at);
  do {
    next = new Date(
      next.getFullYear(),
      next.getMonth(),
      next.getDate() + 1,
      next.getHours(),
      next.getMinutes(),
      0,
      0,
    );
  } while (next.getTime() <= nowMs);
  return next.getTime();
}

// Splits the list at this moment: what rings now, what was missed while the app
// was closed, and what stays (daily alarms move on to their next day).
export function settleAlarms(alarms, nowMs) {
  const due = [];
  const missed = [];
  const remaining = [];
  for (const alarm of normaliseAlarms(alarms)) {
    if (alarm.at > nowMs) {
      remaining.push(alarm);
      continue;
    }
    (nowMs - alarm.at > MISSED_AFTER_MS ? missed : due).push(alarm);
    if (alarm.repeat === "daily") remaining.push({ ...alarm, at: nextDaily(alarm.at, nowMs) });
  }
  return { due, missed, remaining: normaliseAlarms(remaining) };
}

export function describeAlarm(alarm, now = new Date()) {
  const at = new Date(alarm.at);
  const label = alarm.label ? `: ${alarm.label}` : "";
  if (alarm.kind === "timer") {
    return `Timer${label}, ${describeDuration(Math.max(0, alarm.at - now.getTime()))} left`;
  }
  const every = alarm.repeat === "daily" ? "every day at " : "";
  const moment = alarm.repeat === "daily" ? formatClock(at) : formatMoment(at, now);
  return `${alarm.kind === "reminder" ? "Reminder" : "Alarm"} ${every}${moment}${label}`;
}

export function ringText(alarm) {
  if (alarm.kind === "timer")
    return alarm.label ? `Time is up for ${alarm.label}.` : "Time is up. Your timer is done.";
  if (alarm.kind === "reminder") return `Reminder: ${alarm.label || "it is time"}.`;
  return alarm.label
    ? `Your alarm: ${alarm.label}. It is ${formatClock(new Date(alarm.at))}.`
    : `Your alarm is ringing. It is ${formatClock(new Date(alarm.at))}.`;
}

// Which entries a "cancel …" request means. An empty result means nothing matched.
export function matchAlarms(alarms, command, now = new Date()) {
  const list = normaliseAlarms(alarms).filter((alarm) => alarm.kind === command.what);
  if (!command.which) return command.all || list.length === 1 ? list : [];
  const which = command.which.toLowerCase();
  const when = parseWhen(command.which, now, { bareTime: true });
  return list.filter((alarm) => {
    if (alarm.label && alarm.label.toLowerCase().includes(which)) return true;
    if (!when || !when.hasTime) return false;
    const at = new Date(alarm.at);
    return at.getHours() === when.at.getHours() && at.getMinutes() === when.at.getMinutes();
  });
}
