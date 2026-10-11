/**
 * Voice and text command parsing for Weronika's technical viewer and address title.
 * Kept free of DOM and Three.js so it can be tested directly.
 */

export const DEFAULT_ADDRESS_NAME = "Commander";

const KNOWN_OBJECTS = [
  {
    kind: "car",
    label: "Car",
    hindi: "कार",
    words: ["car", "cars", "automobile", "sedan", "कार", "गाड़ी", "गाडी", "gaadi", "gadi"],
  },
  {
    kind: "bike",
    label: "Motorcycle",
    hindi: "बाइक",
    words: ["bike", "bicycle", "motorcycle", "motorbike", "scooter", "बाइक", "साइकिल", "मोटरसाइकिल"],
  },
  {
    kind: "armor",
    label: "Armor suit",
    hindi: "कवच",
    words: ["iron man", "ironman", "armor", "armour", "powered armor", "suit", "कवच", "आयरन मैन"],
  },
  {
    kind: "helicopter",
    label: "Helicopter",
    hindi: "हेलीकॉप्टर",
    words: ["helicopter", "chopper", "heli", "हेलीकॉप्टर"],
  },
  {
    kind: "plane",
    label: "Plane",
    hindi: "विमान",
    words: ["plane", "airplane", "aircraft", "jet", "aeroplane", "विमान", "हवाई जहाज"],
  },
  {
    kind: "ship",
    label: "Ship",
    hindi: "जहाज",
    words: ["ship", "ships", "boat", "boats", "vessel", "cruise", "जहाज", "नौका"],
  },
  {
    kind: "robot",
    label: "Robot",
    hindi: "रोबोट",
    words: ["robot", "android", "humanoid", "रोबोट"],
  },
  {
    kind: "machine",
    label: "Machine",
    hindi: "मशीन",
    words: ["machine", "मशीन"],
  },
];

const ACTION_RE =
  /\b(open|show|display|launch|view|pull up|bring up|load|reveal|kholo|dikhao|dikha|khol)\b|खोलो|दिखाओ|खोल दो|दिखा दो|दिखा|खोल/;
const ARTIFACT_RE =
  /\b(blueprint|blueprints|blue print|wireframe|schematic|technical model|exploded view|3d model|cad model|model)\b|ब्लूप्रिंट|ब्लू प्रिंट|मॉडल|वायरफ्रेम/;

export function sanitizeAddressName(raw) {
  const clean = String(raw ?? "")
    .replace(/[\u0000-\u001f]/g, "")
    .replace(/[<>{}]/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 40);
  return clean || DEFAULT_ADDRESS_NAME;
}

export function isUnlockSelf(text) {
  const raw = String(text || "");
  const folded = raw
    .toLowerCase()
    .replace(/[!,.?'"]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (!folded && !/अनलॉक|खुद|अपने आप/.test(raw)) return false;
  if (/\b(pc|computer|screen|windows|laptop|phone|workstation)\b/.test(folded)) return false;
  if (/lock (the )?(pc|computer|screen|windows|laptop)/.test(folded)) return false;
  if (
    /unlock yourself|unlock your self|unlock weronika|weronika unlock|unlock yourself weronika/.test(
      folded,
    )
  ) {
    return true;
  }
  if (/khud ko unlock|apne aap ko unlock|apne aap unlock|unlock khud ko/.test(folded)) return true;
  if (/अनलॉक/.test(raw) && /(खुद|अपने आप|अपनेआप)/.test(raw)) return true;
  return false;
}

export function isCloseBlueprint(text) {
  const folded = String(text || "")
    .toLowerCase()
    .replace(/[!,.?'"]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  return /^(close|exit|hide|leave) (the )?(blueprint|model|wireframe|schematic|technical view)$/.test(
    folded,
  );
}

function hasWord(text, word) {
  if (/[^\u0000-\u007f]/.test(word)) return text.includes(word);
  const re = new RegExp(`(?:^|[^a-z0-9])${word}(?=$|[^a-z0-9])`, "i");
  return re.test(text);
}

function matchKnown(text) {
  const lower = text.toLowerCase();
  for (const entry of KNOWN_OBJECTS) {
    if (entry.words.some((word) => hasWord(lower, word) || hasWord(text, word))) return entry;
  }
  return null;
}

function cleanSubject(value) {
  return String(value || "")
    .replace(/[?.!,"']+$/g, "")
    .replace(/\b(please|kholo|dikhao|dikha|khol|do|karo|kar do)\b/gi, "")
    .replace(/(खोलो|दिखाओ|करो|कर दो)/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function titleCase(value) {
  return value.replace(/\b[a-z]/g, (letter) => letter.toUpperCase());
}

function extractSubject(text) {
  const patterns = [
    /(?:blueprint|blue print|wireframe|schematic|technical model|3d model|cad model|model)\s+of\s+(?:a|an|the)?\s*(.+)$/i,
    /(?:open|show|display|launch|view|pull up|bring up)\s+(?:me\s+)?(?:a|an|the\s+)?(.+?)\s+(?:blueprint|blue print|wireframe|schematic|technical model|3d model|model)\b/i,
    /(?:ब्लूप्रिंट|मॉडल)\s*(?:का|की|के)?\s*(.+)$/,
    /^(.+?)\s+(?:का|की)\s*(?:ब्लूप्रिंट|मॉडल)/,
  ];
  for (const pattern of patterns) {
    const match = text.match(pattern);
    if (match && match[1]) {
      const subject = cleanSubject(match[1]);
      if (subject && !/^(blueprint|model|wireframe|schematic)$/i.test(subject)) return subject;
    }
  }
  return "";
}

function hasBlueprintIntent(text) {
  return ACTION_RE.test(text) && ARTIFACT_RE.test(text);
}

/**
 * Returns null when the utterance is not a technical-viewer command.
 * Unknown objects still open the safe generic machine, labeled with the request.
 */
export function parseBlueprintCommand(text) {
  const raw = String(text || "").trim();
  if (!raw) return null;
  if (/\brole model\b/i.test(raw)) return null;
  if (isUnlockSelf(raw)) return { action: "unlock" };
  if (isCloseBlueprint(raw)) return { action: "close" };
  if (!hasBlueprintIntent(raw)) return null;

  const known = matchKnown(raw);
  if (known && known.kind !== "machine") {
    return {
      action: "open",
      kind: known.kind,
      label: known.label,
      hindi: known.hindi,
      fallback: false,
    };
  }
  if (known && known.kind === "machine" && !extractSubject(raw)) {
    return {
      action: "open",
      kind: "machine",
      label: "Machine",
      hindi: "मशीन",
      fallback: false,
    };
  }

  const subject = extractSubject(raw);
  const subjectKnown = subject ? matchKnown(subject) : null;
  if (subjectKnown && subjectKnown.kind !== "machine") {
    return {
      action: "open",
      kind: subjectKnown.kind,
      label: subjectKnown.label,
      hindi: subjectKnown.hindi,
      fallback: false,
    };
  }

  const label = subject ? titleCase(subject).slice(0, 42) : known ? known.label : "Machine";
  return {
    action: "open",
    kind: "machine",
    label,
    hindi: label,
    fallback: label.toLowerCase() !== "machine",
  };
}

export function parseExplodeCommand(text) {
  const folded = String(text || "")
    .toLowerCase()
    .replace(/[!,.?'"]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (!folded) return null;
  if (/\b(assemble|collapse|put (it|them|the parts) together|join (it|the parts)|restore parts)\b/.test(folded)) {
    return "assemble";
  }
  if (/(वापस जोड़|जोड़ दो|असेंबल)/.test(text)) return "assemble";
  if (/\b(explode|exploded view|pull apart|separate (the )?parts)\b/.test(folded)) return "explode";
  if (/(अलग कर|एक्सप्लोड|खोल कर दिखा)/.test(text)) return "explode";
  return null;
}
