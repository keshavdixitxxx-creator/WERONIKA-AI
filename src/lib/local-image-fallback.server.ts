function escapeXml(value: string) {
  return value.replace(/[&<>"']/g, (char) => {
    const entities: Record<string, string> = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&apos;",
    };
    return entities[char] ?? char;
  });
}

function vehicleIllustration(prompt: string) {
  const caption = escapeXml(prompt.slice(0, 72));
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 800" role="img" aria-label="Local vector illustration of ${caption}">
  <defs>
    <linearGradient id="sky" x2="0" y2="1"><stop stop-color="#09152d"/><stop offset=".58" stop-color="#22446c"/><stop offset="1" stop-color="#f09b65"/></linearGradient>
    <linearGradient id="road" x2="0" y2="1"><stop stop-color="#25344b"/><stop offset="1" stop-color="#101827"/></linearGradient>
    <linearGradient id="paint" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#fff0b7"/><stop offset=".24" stop-color="#ffbd54"/><stop offset=".62" stop-color="#ef6a35"/><stop offset="1" stop-color="#9b2d42"/></linearGradient>
    <linearGradient id="glass" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#d4f7ff" stop-opacity=".96"/><stop offset=".52" stop-color="#71b7d2" stop-opacity=".88"/><stop offset="1" stop-color="#183452"/></linearGradient>
    <radialGradient id="sun"><stop stop-color="#fff4c7" stop-opacity=".9"/><stop offset="1" stop-color="#ffb165" stop-opacity="0"/></radialGradient>
    <filter id="soft"><feGaussianBlur stdDeviation="26"/></filter>
    <filter id="shadow" x="-.2" y="-.5" width="1.4" height="2"><feGaussianBlur stdDeviation="18"/></filter>
  </defs>
  <rect width="1200" height="800" fill="url(#sky)"/>
  <circle cx="925" cy="250" r="185" fill="url(#sun)"/>
  <circle cx="925" cy="250" r="83" fill="#ffd99b" opacity=".72"/>
  <path d="M0 448 144 372l92 54 129-104 146 122 124-83 136 91 113-119 159 129 92-68 65 43v160H0Z" fill="#142642" opacity=".83"/>
  <path d="M0 505 183 441l140 51 135-65 160 81 184-91 133 74 156-53 109 55v91H0Z" fill="#203957" opacity=".84"/>
  <path d="M0 543h1200v257H0z" fill="url(#road)"/>
  <path d="M0 555h1200" stroke="#ffd28a" stroke-opacity=".48" stroke-width="3"/>
  <path d="M-80 758 379 555h43L82 800M490 800l244-245h43L575 800m263 0 155-245h39L972 800" fill="#dbe7f5" opacity=".12"/>
  <ellipse cx="606" cy="604" rx="424" ry="58" fill="#03070e" opacity=".6" filter="url(#shadow)"/>
  <g>
    <path d="M172 523 207 453q13-27 53-37l119-29 81-75q24-22 61-22h184q46 0 77 31l94 91 89 27q40 13 50 52l8 36q5 26-22 31H194q-32 0-29-30Z" fill="url(#paint)" stroke="#ffe0a0" stroke-opacity=".82" stroke-width="5"/>
    <path d="m408 381 71-64q17-15 42-15h79v94H377Z" fill="url(#glass)" stroke="#fff1cb" stroke-opacity=".72" stroke-width="4"/>
    <path d="M619 302h87q31 0 52 22l77 72H619Z" fill="url(#glass)" stroke="#fff1cb" stroke-opacity=".72" stroke-width="4"/>
    <path d="M603 305v248" stroke="#8b3440" stroke-opacity=".7" stroke-width="7"/>
    <path d="M247 438 351 412m494 1 58 41" fill="none" stroke="#fff0c4" stroke-opacity=".8" stroke-width="6" stroke-linecap="round"/>
    <path d="m201 492 68-9-20 32h-60m802-17 53 9 7 29h-62" fill="#fff2be"/>
    <path d="M197 537h815" stroke="#5e2a37" stroke-width="8" opacity=".8"/>
    <path d="M492 481h151" stroke="#ffe2a3" stroke-opacity=".85" stroke-width="5" stroke-linecap="round"/>
    <path d="M754 478h48" stroke="#ffe2a3" stroke-opacity=".85" stroke-width="5" stroke-linecap="round"/>
    <g>
      <circle cx="353" cy="535" r="79" fill="#090e18" stroke="#b8c5d4" stroke-width="7"/>
      <circle cx="353" cy="535" r="49" fill="#7d91a4" stroke="#dce7ed" stroke-width="7"/>
      <circle cx="353" cy="535" r="18" fill="#172338"/>
      <path d="M353 490v90m-45-45h90m-77-32 64 64m0-64-64 64" stroke="#d7e0e8" stroke-width="8" stroke-linecap="round"/>
    </g>
    <g>
      <circle cx="858" cy="535" r="79" fill="#090e18" stroke="#b8c5d4" stroke-width="7"/>
      <circle cx="858" cy="535" r="49" fill="#7d91a4" stroke="#dce7ed" stroke-width="7"/>
      <circle cx="858" cy="535" r="18" fill="#172338"/>
      <path d="M858 490v90m-45-45h90m-77-32 64 64m0-64-64 64" stroke="#d7e0e8" stroke-width="8" stroke-linecap="round"/>
    </g>
  </g>
  <text x="58" y="74" fill="#d8edff" font-family="Arial,sans-serif" font-size="17" letter-spacing="5">WERONIKA · LOCAL VECTOR FALLBACK</text>
  <text x="60" y="733" fill="#fff1ce" font-family="Arial,sans-serif" font-size="23" font-weight="600" textLength="900" lengthAdjust="spacingAndGlyphs">${caption}</text>
  <text x="60" y="770" fill="#cfdeee" font-family="Arial,sans-serif" font-size="13" letter-spacing="2">AI IMAGE REQUEST FAILED · ILLUSTRATION DRAWN LOCALLY</text>
</svg>`;
}

function promptPoster(prompt: string) {
  const caption = escapeXml(prompt.slice(0, 88));
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 800" role="img" aria-label="Local visual preview for ${caption}">
  <defs><linearGradient id="bg" x2="1" y2="1"><stop stop-color="#08162d"/><stop offset=".55" stop-color="#30205c"/><stop offset="1" stop-color="#087e91"/></linearGradient><radialGradient id="glow"><stop stop-color="#ffcc70" stop-opacity=".85"/><stop offset="1" stop-color="#ffcc70" stop-opacity="0"/></radialGradient><filter id="blur"><feGaussianBlur stdDeviation="48"/></filter></defs>
  <rect width="1200" height="800" fill="url(#bg)"/><circle cx="890" cy="270" r="210" fill="url(#glow)"/><circle cx="300" cy="580" r="180" fill="#3b91e8" opacity=".5" filter="url(#blur)"/>
  <path d="M0 618q212-128 416-24t410-19 374-2v227H0z" fill="#071323" opacity=".68"/><rect x="70" y="92" width="1060" height="616" rx="34" fill="#07101e" fill-opacity=".34" stroke="#d8f4ff" stroke-opacity=".45" stroke-width="2"/>
  <text x="120" y="166" fill="#b8eaff" font-family="Arial,sans-serif" font-size="17" letter-spacing="6">WERONIKA · LOCAL PROMPT PREVIEW</text>
  <text x="120" y="362" fill="#fff4dc" font-family="Arial,sans-serif" font-size="52" font-weight="700">${caption}</text>
  <text x="120" y="430" fill="#d4e8f5" font-family="Arial,sans-serif" font-size="22">Cloud image request failed.</text>
  <text x="120" y="478" fill="#d4e8f5" font-family="Arial,sans-serif" font-size="18">This fallback is a local vector artwork card, not an AI-generated image.</text>
</svg>`;
}

export function localImageFallback(prompt: string, reason: string) {
  const safePrompt = Array.from(prompt, (char) => {
    const codePoint = char.codePointAt(0) ?? 0;
    return codePoint < 0x20 || codePoint === 0x7f ? " " : char;
  })
    .join("")
    .replace(/\s+/g, " ")
    .trim();
  const normalized = safePrompt.toLowerCase();
  const svg = /\b(car|cars|vehicle|automobile|sedan|truck|van|jeep|motorcycle|bike)\b/.test(
    normalized,
  )
    ? vehicleIllustration(safePrompt)
    : promptPoster(safePrompt);
  const fallbackError = reason.replace(/\s+/g, " ").trim().slice(0, 220);
  return {
    image: `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`,
    prompt,
    fallback: true,
    warning: `Cloud image generation failed${fallbackError ? `: ${fallbackError}` : "."} Displaying a locally drawn SVG fallback instead.`,
  };
}
