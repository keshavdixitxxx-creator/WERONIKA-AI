const ENGINE_HINTS = [
  { kind: "image", pattern: /\bflux(?:\s*\.\s*1)?\b/i, label: "FLUX 1 (ComfyUI)" },
  { kind: "image", pattern: /\bsdxl\b|stable\s*diffusion\s*xl/i, label: "SDXL (ComfyUI / Forge)" },
  {
    kind: "image",
    pattern: /\bcomfy\s*ui\b/i,
    label: "ComfyUI (select an installed FLUX or SDXL checkpoint)",
  },
  {
    kind: "image",
    pattern: /\bforge\b/i,
    label: "Forge (select an installed SDXL or FLUX checkpoint)",
  },
  { kind: "video", pattern: /\bwan\s*2(?:\.\s*1)?\b/i, label: "Wan 2.1 (local video workflow)" },
  {
    kind: "video",
    pattern: /\bltx(?:\s*[- ]\s*video)?\b/i,
    label: "LTX-Video (local video workflow)",
  },
  { kind: "video", pattern: /\banimate\s*diff\b/i, label: "AnimateDiff (local video workflow)" },
  { kind: "song", pattern: /\bace\s*[- ]?\s*step\b/i, label: "ACE-Step (local audio weights)" },
  { kind: "song", pattern: /\byue\s*2\b/i, label: "YuE2 (local audio weights)" },
  {
    kind: "song",
    pattern: /\bdiff\s*[- ]?\s*rhythm\b/i,
    label: "DiffRhythm (local audio weights)",
  },
];

const DEFAULT_ENGINES = {
  image: "ComfyUI / Forge (SDXL default; choose FLUX if installed)",
  video: "ComfyUI with Wan 2.1, LTX-Video, or AnimateDiff",
  song: "ACE-Step, YuE2, or DiffRhythm local weights",
};

const KIND_PATTERNS = {
  image:
    /\b(?:image|picture|photo|artwork|illustration|drawing|wallpaper|icon|logo|poster|cover|screenshot|flux|sdxl|stable\s*diffusion|comfy\s*ui|forge)\b|तस्वीर|फोटो|इमेज|चित्र/i,
  video:
    /\b(?:video|clip|reel|animation|film|wan\s*2(?:\.\s*1)?|ltx(?:\s*[- ]\s*video)?|animate\s*diff)\b|वीडियो|क्लिप/i,
  song: /\b(?:song|music|track|melody|tune|audio|lyrics|beat|ace\s*[- ]?\s*step|yue\s*2|diff\s*[- ]?\s*rhythm)\b|गाना|गीत|संगीत/i,
};

const PROMPT_INTENT =
  /\b(?:prompt|brief|spec(?:ification)?|settings|workflow|motion\s+sequence)\b/i;
const LOCAL_INTENT =
  /\b(?:local(?:ly)?|on\s+my\s+(?:pc|computer|machine)|run\s+(?:it\s+)?locally|offline|local\s+model)\b/i;
const GENERATION_INTENT =
  /\b(?:make|create|generate|write|compose|prepare|build|design|draft|give\s+me|need)\b/i;

export function detectLocalMediaRequest(raw) {
  const text = String(raw || "").trim();
  if (!text) return null;
  let engine = ENGINE_HINTS.find((entry) => entry.pattern.test(text));
  const hasLocalIntent = LOCAL_INTENT.test(text);
  const hasPromptIntent = PROMPT_INTENT.test(text);
  const hasGenerationIntent = GENERATION_INTENT.test(text);
  if (engine && !hasLocalIntent && !hasPromptIntent) {
    if (
      /^Forge\b/i.test(engine.label) &&
      !/\b(?:with|using|via|in)\s+(?:the\s+)?forge\b/i.test(text)
    )
      engine = undefined;
    if (
      /^FLUX\b/i.test(engine?.label || "") &&
      !/\b(?:with|using|via|in|for)\s+(?:the\s+)?flux\b|\bflux\s*(?:\.\s*1|dev|schnell|model|workflow|checkpoint)\b/i.test(
        text,
      )
    )
      engine = undefined;
  }
  const softwareProduct =
    /\b(?:website|web\s*(?:app|page)|app(?:lication)?|player|editor|dashboard|program|script|source\s+code|api|software)\b/i.test(
      text,
    );
  const explicitArtifact =
    /\b(?:image|picture|photo|artwork|illustration|drawing|wallpaper|video|clip|reel|animation)\s+(?:of|showing|about|prompt|generation|sequence)\b|\b(?:icon|logo|screenshot|cover|wallpaper|poster|illustration|drawing)\b/i.test(
      text,
    );
  if (softwareProduct && hasGenerationIntent && !hasPromptIntent && !explicitArtifact) return null;
  if (!hasLocalIntent && !hasPromptIntent && !engine) return null;
  if (!hasPromptIntent && !(hasGenerationIntent && (hasLocalIntent || engine))) return null;

  let kind = engine?.kind || "";
  if (!kind) kind = Object.keys(KIND_PATTERNS).find((key) => KIND_PATTERNS[key].test(text)) || "";
  if (!kind) return null;

  return {
    kind,
    engine: engine?.label || DEFAULT_ENGINES[kind],
    request: text,
  };
}

export function buildLocalMediaInstruction({ kind, engine, request, language = "en" }) {
  const common = [
    "Create a detailed, ready-to-copy TEXT BRIEF for a locally run generative model. Do not generate media, call a cloud route, claim that a file was generated, or add an introduction/conclusion.",
    `Requested subject and constraints (preserve their meaning): ${String(request || "").slice(0, 1800)}`,
    `Target local workflow: ${engine || DEFAULT_ENGINES[kind]}. Keep the exact bracketed section headings below. Output in concise English for compatibility with local model interfaces; keep proper names and requested quoted text unchanged.`,
    "Use practical defaults when the user did not specify a value. Do not invent a source image, a specific real person, or a model checkpoint that the user did not provide.",
  ];

  if (kind === "image") {
    common.push(
      "Return only these sections, each on its own line: [Target Local Workflow], [Positive Prompt], [Negative Prompt], [Sampler], [Steps: N], [CFG Scale], [Seed], [Resolution].",
      "Use a step count from 20 through 30. For SDXL, default to DPM++ 2M Karras, 25 steps, CFG 6.5, seed -1 (random), and 1024x1024 unless aspect ratio is requested. For FLUX, use Euler, 25 steps, seed -1, and 1024x1024; set guidance around 3.5 and label it as FLUX guidance (not classic SDXL CFG). Include a useful negative prompt while noting only if the selected FLUX workflow ignores it. Match portrait/landscape aspect ratio to the request.",
    );
  } else if (kind === "video") {
    common.push(
      "Return only these sections, each on its own line: [Target Local Workflow], [Source Frame/Image Reference], [Camera Motion Vector], [Subject Action], [FPS: 24], [Frame Count: N], [Denoising Strength], [Negative Prompt].",
      "Keep FPS exactly 24. Choose an integer frame count from 16 through 81 based on the requested duration (use 49 frames, about 2.04 seconds, if unspecified). State whether a source frame was supplied; if none, say text-to-video / no source frame and describe a suitable first frame without pretending an image is attached. Give camera motion as a clear x/y/z vector and define its axes briefly. Give one continuous, physically plausible subject action. Use denoising from 0 to 1 and explain image-to-video versus text-to-video only when needed.",
    );
  } else {
    common.push(
      "Return only these sections: [Target Local Workflow], [Style/Genre Tags], [Tempo/BPM], [Instrument Breakdown], [Lyrics], [Verse], [Chorus], [Outro], [Vocal Gender/Timbre]. Put original, singable lyrics under Verse, Chorus, and Outro; use a memorable chorus and do not quote known songs.",
      `Write the lyrics in the language and script of the user's request (detected language: ${language}; Hinglish remains Latin-script Hinglish). Choose a tempo and instrumentation that fit the request. When not specified, give a concrete, suitable vocal gender/timbre rather than leaving it blank.`,
    );
  }

  return common.join("\n\n");
}

function topicFromRequest(request) {
  const clean = String(request || "a scene matching the request")
    .replace(/\s+/g, " ")
    .trim()
    .replace(
      /^\s*(?:please\s+)?(?:can you\s+)?(?:make|create|generate|write|compose|prepare|build|design|draft|give me)\s+(?:me\s+)?/i,
      "",
    )
    .replace(/^\s*(?:a|an|the)\s+/i, "")
    .replace(/\b(?:local|structured|detailed|ready[- ]to[- ]copy)\b/gi, " ")
    .replace(
      /\b(?:comfy\s*ui|forge|sdxl|stable\s*diffusion(?:\s*xl)?|flux(?:\s*1)?|wan\s*2(?:\.\s*1)?|ltx(?:\s*[- ]\s*video)?|animate\s*diff|ace\s*[- ]?\s*step|yue\s*2|diff\s*[- ]?\s*rhythm)\b/gi,
      " ",
    )
    .replace(
      /\b(?:image|picture|photo|artwork|illustration|video|clip|reel|animation|music|song|track|motion\s+sequence)?\s*(?:generation\s*)?(?:prompt|brief|spec(?:ification)?)\b/gi,
      " ",
    )
    .replace(/^\s*(?:for|of|about|showing|depicting|:|-)\s*/i, "")
    .replace(/^\s*(?:a|an|the)\s+/i, "")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 700);
  return clean || "a scene matching the request";
}

export function createLocalMediaFallback({ kind, engine, request }) {
  const topic = topicFromRequest(request);
  const target = engine || DEFAULT_ENGINES[kind];
  if (kind === "image") {
    const flux = /\bflux\b/i.test(target) && !/\bsdxl\b/i.test(target);
    const portrait = /\b(?:portrait|vertical|9\s*:\s*16|phone wallpaper|story)\b/i.test(topic);
    const landscape = /\b(?:landscape|wide|16\s*:\s*9|cinematic wide|youtube)\b/i.test(topic);
    const resolution = portrait ? "832x1216" : landscape ? "1216x832" : "1024x1024";
    return [
      `[Target Local Workflow] ${target}`,
      `[Positive Prompt] ${topic}; clear focal subject, intentional composition, coherent perspective, natural material detail, balanced lighting, refined color palette, high-quality finish, no unintended text.`,
      "[Negative Prompt] low quality, blurry, distorted anatomy, extra or missing limbs, malformed hands, duplicate subject, unwanted text, watermark, logo, compression artifacts, oversharpening",
      `[Sampler] ${flux ? "Euler" : "DPM++ 2M Karras"}`,
      "[Steps: 25]",
      flux
        ? "[CFG Scale] 3.5 (FLUX guidance; use the workflow's FluxGuidance control, not classic SDXL CFG)"
        : "[CFG Scale] 6.5",
      "[Seed] -1 (random; replace with a fixed integer for reproducibility)",
      `[Resolution] ${resolution}`,
    ].join("\n\n");
  }

  if (kind === "video") {
    const framesMatch = topic.match(/\b(\d+(?:\.\d+)?)\s*(?:seconds?|secs?|s)\b/i);
    const seconds = framesMatch ? Number(framesMatch[1]) : 49 / 24;
    const frames = Math.min(81, Math.max(16, Math.round(seconds * 24)));
    return [
      `[Target Local Workflow] ${target}`,
      `[Source Frame/Image Reference] None supplied; use text-to-video. First frame should establish: ${topic}. If using image-to-video, load a matching still in the local engine.`,
      "[Camera Motion Vector] x=0.00, y=0.00, z=+0.12 (normalized clip-relative motion; x right, y up, z toward subject; slow push-in)",
      `[Subject Action] ${topic}; one continuous, readable action with natural timing and believable physics; no cuts.`,
      "[FPS: 24]",
      `[Frame Count: ${frames}] (${frames}/24 seconds; allowed range 16-81)`,
      "[Denoising Strength] 0.60 for image-to-video to preserve the source frame; for text-to-video with no source image, follow the workflow's full-denoise/default setting (often 1.00).",
      "[Negative Prompt] flicker, jitter, sudden cuts, subject identity drift, warped geometry, duplicated subjects, unstable background, unintended text or watermark",
    ].join("\n\n");
  }

  return [
    `[Target Local Workflow] ${target}`,
    "[Style/Genre Tags] warm, melodic, emotionally clear, contemporary indie-pop; adapt the mood and genre to this request",
    "[Tempo/BPM] 92 BPM, 4/4 (adjust to the requested mood)",
    "[Instrument Breakdown] Intro: soft piano and ambient pad; Verse: add muted bass and restrained percussion; Chorus: fuller drums, warm bass, and light guitar/synth accents; Outro: return to piano and let the final chord ring.",
    "[Lyrics]",
    `[Verse] I kept a little hope beside me through the changing days; ${topic}`,
    "[Chorus] We find our way, one heartbeat at a time; even in the dark, a little light can shine.",
    "[Outro] Let the last note breathe; tomorrow starts again.",
    "[Vocal Gender/Timbre] Warm, intimate mid-range lead vocal; choose a feminine or masculine voice to match the user's preference, with clear diction and gentle dynamics.",
  ].join("\n\n");
}

export function normalizeLocalMediaBrief(kind, candidate, context) {
  let text = String(candidate || "")
    .trim()
    .replace(/^```[^\r\n]*\r?\n/, "")
    .replace(/\r?\n?```\s*$/, "")
    .trim();
  const base = createLocalMediaFallback({ ...context, kind });
  const headings = {
    image: [
      /\[\s*Target Local Workflow\s*\]/i,
      /\[\s*Positive Prompt\s*\]/i,
      /\[\s*Negative Prompt\s*\]/i,
      /\[\s*Sampler\s*\]/i,
      /\[\s*Steps\s*:\s*(?:2\d|30)\b[^\]]*\]/i,
      /\[\s*CFG Scale\s*\]/i,
      /\[\s*Seed\s*\]/i,
      /\[\s*Resolution\s*\]/i,
    ],
    video: [
      /\[\s*Target Local Workflow\s*\]/i,
      /\[\s*Source Frame\/Image Reference\s*\]/i,
      /\[\s*Camera Motion Vector\s*\]/i,
      /\[\s*Subject Action\s*\]/i,
      /\[\s*FPS\s*:\s*24\s*\]/i,
      /\[\s*Frame Count\s*:\s*(\d+)\s*\]/i,
      /\[\s*Denoising Strength\s*\]/i,
      /\[\s*Negative Prompt\s*\]/i,
    ],
    song: [
      /\[\s*Target Local Workflow\s*\]/i,
      /\[\s*Style\/Genre Tags\s*\]/i,
      /\[\s*Tempo\/BPM\s*\]/i,
      /\[\s*Instrument Breakdown\s*\]/i,
      /\[\s*Lyrics\s*\]/i,
      /\[\s*Verse\s*\]/i,
      /\[\s*Chorus\s*\]/i,
      /\[\s*Outro\s*\]/i,
      /\[\s*Vocal Gender\/Timbre\s*\]/i,
    ],
  };
  const complete = !!text && (headings[kind] || []).every((pattern) => pattern.test(text));
  if (kind === "video" && complete) {
    const match = text.match(/\[\s*Frame Count\s*:\s*(\d+)\s*\]/i);
    const frames = Number(match?.[1]);
    if (!Number.isInteger(frames) || frames < 16 || frames > 81) {
      return { text: base, complete: false };
    }
  }
  return complete ? { text, complete: true } : { text: base, complete: false };
}
