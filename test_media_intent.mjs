import assert from "node:assert/strict";
import {
  buildMediaIntentCheck,
  isClearlyNonActionableMediaMessage,
  isExplicitMediaGenerationRequest,
  inferMediaKindFromText,
  mightBeMediaRequest,
  parseMediaIntentResult,
} from "./public/weronika-media-intent.js";

assert.equal(
  mightBeMediaRequest("generate"),
  false,
  "the word generate alone is not a media intent",
);
assert.equal(mightBeMediaRequest("Generate a project report for me"), false);
assert.equal(mightBeMediaRequest("How do I generate an image of a cat?"), false);
assert.equal(isClearlyNonActionableMediaMessage("How can I make a video?"), true);
assert.equal(isClearlyNonActionableMediaMessage("Please don't create a song"), true);
assert.equal(mightBeMediaRequest("Can you generate an image of a cat?"), true);
assert.equal(isExplicitMediaGenerationRequest("Can you generate an image of a cat?"), true);
assert.equal(isExplicitMediaGenerationRequest("How can I generate an image of a cat?"), false);
assert.equal(isExplicitMediaGenerationRequest("Can you generate an image gallery app?"), false);
assert.equal(inferMediaKindFromText("एक बिल्ली की तस्वीर बनाओ"), "image");
assert.equal(inferMediaKindFromText("generate a music video"), "video");
assert.equal(mightBeMediaRequest("image of a red car at sunset"), true);
assert.equal(mightBeMediaRequest("एक बिल्ली की तस्वीर बनाओ"), true);
assert.equal(isExplicitMediaGenerationRequest("एक बिल्ली की तस्वीर बनाओ"), true);
assert.equal(mightBeMediaRequest("Crea una imagen de un gato"), true);
assert.equal(mightBeMediaRequest("Help me write code that generates an image gallery"), true);

const check = buildMediaIntentCheck("एक बिल्ली की तस्वीर बनाओ");
assert.match(check, /original language and script/);
assert.match(check, /"एक बिल्ली की तस्वीर बनाओ"/);

assert.deepEqual(parseMediaIntentResult('{"intent":"chat"}'), { intent: "chat" });
assert.equal(parseMediaIntentResult("not valid JSON"), null);
assert.equal(parseMediaIntentResult('Unrelated quote: {"intent":"media","kind":"image"}'), null);
assert.equal(parseMediaIntentResult('{"intent":"media","kind":"webpage"}'), null);
assert.deepEqual(parseMediaIntentResult('{"intent":"media","kind":"song","prompt":"गीत की धुन"}'), {
  intent: "media",
  kind: "song",
  prompt: "गीत की धुन",
});
assert.deepEqual(
  parseMediaIntentResult('```json\n{"intent":"media","kind":"video","prompt":"A calm ocean"}\n```'),
  { intent: "media", kind: "video", prompt: "A calm ocean" },
);

console.log("media intent classification checks passed");
