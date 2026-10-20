const MEDIA_NOUNS =
  /\b(?:image|picture|photo|pic|artwork|drawing|wallpaper|illustration|song|music|track|melody|tune|video|clip|reel|animation|movie)\b|(?:तस्वीर|फोटो|इमेज|चित्र|गाना|गीत|वीडियो|क्लिप)|\b(?:tasveer|tasvir|chitra|gaana|gana|geet|video|clip|song|music)\b|(?:画像|写真|イラスト|壁紙|歌曲|音乐|视频|影片)|(?:صورة|رسم|أغنية|موسيقى|فيديو)|(?:imagen|foto|ilustración|dibujo|canción|música|vídeo|animación)|(?:image|photo|illustration|chanson|musique|vidéo)|(?:bild|foto|illustration|lied|musik|video)|(?:imagem|canção|música|vídeo)|(?:картинку|изображение|песню|музыку|видео)/iu;

const MEDIA_ACTIONS =
  /\b(?:make|create|generate|draw|paint|design|render|write|compose|sing|shoot|film|produce|animate|build|turn\s+(?:this|it)\s+into)\b|(?:बनाओ|बना\s*दो|बनाकर\s*दो|बनाइए|दिखाओ|गाओ|लिखो|तैयार\s*करो)|\b(?:banao|bana\s*do|dikhao|taiyar\s*karo|likho|gaao|sunaao)\b|\b(?:crea|genera|dibuja|hazme|haz|crée|génère|dessine|fais|erstelle|erzeuge|generiere|zeichne|male|crie|gere|desenha|faça|buatkan|ciptakan|hasilkan|создай|сгенерируй|нарисуй|сделай)\b|(?:作って|生成して|描いて|作成して|创作|制作|生成|أنشئ|اصنع|ارسم|ولّد)/iu;

const BARE_MEDIA_REQUEST =
  /^\s*(?:an?\s+)?(?:image|picture|photo|pic|song|music|track|video|clip|reel|animation)\s+(?:of|about|showing|with|for|:)\s*\S+/iu;
const NON_ACTIONABLE_PREFIX =
  /^\s*(?:how\s+(?:do\s+i|can\s+i|to|does|do\s+you)|what\s+(?:does|is|are)|why\s+(?:does|do|is)|explain\s+how|tell\s+me\s+how|can\s+you\s+explain|i\s+(?:can't|cannot|do\s+not|don't)\s+(?:generate|create|make|draw|compose|sing|film|shoot)|please\s+don't\s+(?:generate|create|make|draw|compose|sing|film|shoot)|(?:मत|नहीं)\s*(?:बनाओ|बनाना|बनाइए))/iu;
const EXPLICIT_ENGLISH_REQUEST =
  /^\s*(?:(?:hey\s+)?(?:weronika|veronika)[,;:\s]+)?(?:please\s+)?(?:(?:can|could|would|will)\s+you\s+(?:please\s+)?|i\s+(?:want|need|would like)\s+you\s+to\s+(?:please\s+)?)?(?:make|create|generate|draw|paint|design|render|write|compose|sing|shoot|film|produce|animate)\b/i;
const EXPLICIT_TRANSLATED_REQUEST =
  /^\s*(?:crea|genera|dibuja|hazme|haz|crée|génère|dessine|fais|erstelle|erzeuge|generiere|zeichne|male|crie|gere|desenha|faça|buat(?:kan)?|ciptakan|hasilkan|создай|сгенерируй|нарисуй|сделай|أنشئ|اصنع|ارسم|ولّد|作って|生成して|描いて|作成して|创作|制作)/iu;
const EXPLICIT_HINDI_REQUEST =
  /^\s*(?:कृपया\s*)?(?:एक\s*)?(?:.+\s)?(?:तस्वीर|फोटो|इमेज|चित्र|गाना|गीत|वीडियो|क्लिप).*?(?:बनाओ|बना\s*दो|बनाकर\s*दो|बनाइए|दिखाओ|गाओ|लिखो|तैयार\s*करो)\s*[.!।?]*$/u;
const EXPLICIT_ROMAN_HINDI_REQUEST =
  /^\s*(?:please\s+)?(?:.+\s)?(?:tasveer|tasvir|chitra|photo|image|gaana|gana|geet|video|clip)\b.*\b(?:banao|bana\s+do|dikhao|taiyar\s+karo|likho|gaao|sunaao)\s*[.!?]*$/i;
const SOFTWARE_REQUEST =
  /\b(?:app|application|website|webpage|software|code|script|program|prompt|tutorial|instructions|workflow|generator|editor)\b/i;

const VIDEO_NOUNS =
  /\b(?:video|clip|reel|animation|movie|film)\b|(?:वीडियो|क्लिप|動画|映像|ビデオ|视频|影片|短片|فيديو|vídeo|animación|vidéo|animation|video|film|анимацию)/iu;
const SONG_NOUNS =
  /\b(?:song|music|track|melody|tune|gaana|gana|geet)\b|(?:गाना|गीत|歌曲|音乐|歌|曲|音楽|أغنية|موسيقى|canción|música|chanson|musique|lied|musik|canção|melodia|canzone|brano|музыку|песню)/iu;
const IMAGE_NOUNS =
  /\b(?:image|picture|photo|pic|artwork|drawing|wallpaper|illustration|tasveer|tasvir|chitra|imagen|foto|dibujo|bild|imagem|resim|görsel|картинку|изображение)\b|(?:तस्वीर|फोटो|इमेज|चित्र|画像|写真|イラスト|壁紙|图片|图像|照片|插画|صورة|رسم|imagen|foto|illustration|imagem|gambar)/iu;
const ALLOWED_KINDS = new Set(["image", "video", "song"]);

/** Obvious how-to, quoted-negation, and refusal turns stay in ordinary chat. */
export function isClearlyNonActionableMediaMessage(value) {
  return NON_ACTIONABLE_PREFIX.test(String(value ?? "").trim());
}

/** High-confidence direct-command fallback for older brain relays without task support. */
export function isExplicitMediaGenerationRequest(value) {
  const text = String(value ?? "").trim();
  if (
    !text ||
    text.length > 4000 ||
    isClearlyNonActionableMediaMessage(text) ||
    SOFTWARE_REQUEST.test(text) ||
    !MEDIA_NOUNS.test(text) ||
    !MEDIA_ACTIONS.test(text)
  )
    return false;
  return (
    EXPLICIT_ENGLISH_REQUEST.test(text) ||
    EXPLICIT_TRANSLATED_REQUEST.test(text) ||
    EXPLICIT_HINDI_REQUEST.test(text) ||
    EXPLICIT_ROMAN_HINDI_REQUEST.test(text)
  );
}

export function inferMediaKindFromText(value) {
  const text = String(value ?? "");
  if (VIDEO_NOUNS.test(text)) return "video";
  if (SONG_NOUNS.test(text)) return "song";
  if (IMAGE_NOUNS.test(text)) return "image";
  return null;
}

/**
 * A cheap lexical prefilter: this never decides to generate. It only decides
 * whether the brain should be asked to classify a possibly media-related turn.
 */
export function mightBeMediaRequest(value) {
  const text = String(value ?? "").trim();
  if (!text || text.length > 4000 || isClearlyNonActionableMediaMessage(text)) return false;
  return MEDIA_NOUNS.test(text) && (MEDIA_ACTIONS.test(text) || BARE_MEDIA_REQUEST.test(text));
}

export function buildMediaIntentCheck(userText) {
  const quoted = JSON.stringify(String(userText ?? "").slice(0, 4000));
  return [
    "Classify the user's intent before any media model is called.",
    "Return exactly one JSON object and no markdown or extra text.",
    'For an explicit, present-tense request for Weronika to create actual media now, return {"intent":"media","kind":"image","prompt":"..."}; kind must be exactly one of "image", "video", or "song".',
    'For every other case return: {"intent":"chat"}.',
    "A media noun or the word generate is not enough. Use chat for questions about how media generation works, capability questions, hypotheticals, quotes, negative requests, requests to write code/prompts/instructions, and unrelated messages that merely mention generation.",
    "The prompt must describe only the requested media, stay in the user's original language and script, and preserve their details without inventing new ones.",
    `User's exact message: ${quoted}`,
  ].join("\n");
}

/** Strictly accepts a parsed brain decision; ambiguous or malformed output means chat. */
export function parseMediaIntentResult(value) {
  if (typeof value !== "string") return null;
  const cleaned = value
    .trim()
    .replace(/^```(?:json)?\s*/i, "")
    .replace(/\s*```$/, "")
    .trim();
  let parsed;
  try {
    parsed = JSON.parse(cleaned);
  } catch {
    return null;
  }
  if (!parsed || typeof parsed !== "object") return null;
  if (parsed.intent === "chat") return { intent: "chat" };
  if (parsed.intent !== "media") return null;
  const kind = String(parsed.kind ?? "").toLowerCase();
  if (!ALLOWED_KINDS.has(kind)) return null;
  const prompt = typeof parsed.prompt === "string" ? parsed.prompt.trim().slice(0, 4000) : "";
  return { intent: "media", kind, prompt };
}
