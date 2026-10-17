import assert from "node:assert/strict";
import {
  parseBlueprintCommand,
  sanitizeAddressName,
  DEFAULT_ADDRESS_NAME,
} from "./public/weronika-commands.js";

const cases = [
  ["open blueprint of a car", "car", false],
  ["show bike model", "bike", false],
  ["show the robot wireframe", "robot", false],
  ["open blueprint of a toaster", "machine", true],
  ["कार का ब्लूप्रिंट खोलो", "car", false],
  ["बाइक का मॉडल दिखाओ", "bike", false],
  ["रोबोट का ब्लूप्रिंट दिखाओ", "robot", false],
  ["car ka blueprint kholo", "car", false],
  ["bike ka model dikhao", "bike", false],
  ["show iron man model", "armor", false],
  ["open blueprint of a helicopter", "helicopter", false],
  ["show plane model", "plane", false],
  ["open blueprint of a ship", "ship", false],
];

for (const [text, kind, fallback] of cases) {
  const command = parseBlueprintCommand(text);
  assert.equal(command && command.action, "open", text);
  assert.equal(command.kind, kind, text);
  assert.equal(command.fallback, fallback, text);
}

assert.equal(parseBlueprintCommand("Weronika, unlock yourself").action, "unlock");
assert.equal(parseBlueprintCommand("वेरोनिका अपने आप को अनलॉक करो").action, "unlock");
assert.equal(parseBlueprintCommand("unlock the pc"), null);
assert.equal(parseBlueprintCommand("hello there"), null);
assert.equal(sanitizeAddressName("  "), DEFAULT_ADDRESS_NAME);
assert.equal(sanitizeAddressName("Captain <script>"), "Captain script");
assert.equal(sanitizeAddressName("x".repeat(80)).length, 40);

console.log("command checks passed");
