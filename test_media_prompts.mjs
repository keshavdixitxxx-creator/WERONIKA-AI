import assert from "node:assert/strict";
import {
  buildLocalMediaInstruction,
  createLocalMediaFallback,
  detectLocalMediaRequest,
  normalizeLocalMediaBrief,
} from "./public/weronika-local-prompts.js";

const image = detectLocalMediaRequest("Write a local FLUX image prompt of a silver car at sunset");
assert.equal(image?.kind, "image");
assert.match(image.engine, /FLUX/i);
const explicitImagePrompt = detectLocalMediaRequest(
  "Write a local FLUX image prompt of a silver car at sunset",
);
assert.ok(
  createLocalMediaFallback(explicitImagePrompt).includes("[Positive Prompt] silver car at sunset"),
);
assert.equal(detectLocalMediaRequest("Generate an image of a silver car at sunset"), null);
assert.equal(detectLocalMediaRequest("Create a picture of a blacksmith at a forge"), null);
assert.equal(detectLocalMediaRequest("Create an image using Forge of a silver car")?.kind, "image");
assert.equal(detectLocalMediaRequest("Create an image of a flux capacitor"), null);
assert.equal(detectLocalMediaRequest("I use a local FLUX image model"), null);
assert.equal(detectLocalMediaRequest("Make a local music player app"), null);
assert.equal(detectLocalMediaRequest("Build a local image generator app"), null);
assert.equal(
  detectLocalMediaRequest("Make a local video prompt of a website launch")?.kind,
  "video",
);
assert.equal(
  detectLocalMediaRequest("Create a local app icon prompt for a space explorer")?.kind,
  "image",
);

const video = detectLocalMediaRequest(
  "Create a Wan 2.1 motion sequence prompt: a red car drives through rain",
);
assert.equal(video?.kind, "video");
assert.match(video.engine, /Wan 2\.1/i);

const song = detectLocalMediaRequest(
  "Write an ACE-Step local music brief for a hopeful song about starting over",
);
assert.equal(song?.kind, "song");
assert.match(song.engine, /ACE-Step/i);

const imageFallback = createLocalMediaFallback(image);
for (const section of [
  "[Positive Prompt]",
  "[Negative Prompt]",
  "[Sampler]",
  "[Steps: 25]",
  "[CFG Scale]",
  "[Seed]",
  "[Resolution]",
])
  assert.ok(imageFallback.includes(section), `missing image section ${section}`);

const defaultImage = detectLocalMediaRequest(
  "Write a local image prompt for a mountain cabin at dawn",
);
assert.ok(createLocalMediaFallback(defaultImage).includes("[Sampler] DPM++ 2M Karras"));
assert.ok(createLocalMediaFallback(defaultImage).includes("[CFG Scale] 6.5"));

const videoFallback = createLocalMediaFallback(video);
for (const section of [
  "[Source Frame/Image Reference]",
  "[Camera Motion Vector]",
  "[Subject Action]",
  "[FPS: 24]",
  "[Frame Count:",
  "[Denoising Strength]",
])
  assert.ok(videoFallback.includes(section), `missing video section ${section}`);
const frameCount = Number(videoFallback.match(/\[Frame Count: (\d+)\]/)?.[1]);
assert.ok(frameCount >= 16 && frameCount <= 81);

const songFallback = createLocalMediaFallback(song);
for (const section of [
  "[Style/Genre Tags]",
  "[Tempo/BPM]",
  "[Instrument Breakdown]",
  "[Verse]",
  "[Chorus]",
  "[Outro]",
  "[Vocal Gender/Timbre]",
])
  assert.ok(songFallback.includes(section), `missing music section ${section}`);

const instruction = buildLocalMediaInstruction({
  kind: "image",
  engine: image.engine,
  request: "cat ".repeat(500),
});
assert.ok(instruction.length < 8_000, "local prompt request should fit the brain API limit");

const invalid = normalizeLocalMediaBrief("image", "not a structured prompt", image);
assert.equal(invalid.complete, false);
assert.ok(invalid.text.includes("[Steps: 25]"));

const completeImage = normalizeLocalMediaBrief(
  "image",
  "[Target Local Workflow] FLUX\n[Positive Prompt] cat\n[Negative Prompt] blur\n[Sampler] Euler\n[Steps: 25]\n[CFG Scale] 3.5\n[Seed] -1\n[Resolution] 1024x1024",
  image,
);
assert.equal(completeImage.complete, true);

console.log("local media prompt checks passed");
