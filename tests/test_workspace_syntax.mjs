import assert from "node:assert/strict";
import fs from "node:fs";
import {
  HIGHLIGHT_LIMIT,
  escapeHtml,
  highlightCode,
  languageForPath,
} from "../public/workspace-syntax.js";

// The coloured layer sits exactly on top of the text area, so colouring must never
// add, drop, or reorder a character.
function plain(html) {
  return html
    .replace(/<span class="tk-[a-z]">/g, "")
    .replace(/<\/span>/g, "")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&");
}
function assertFaithful(text, language, label = language) {
  const html = highlightCode(text, language);
  assert.equal(plain(html), text, `${label}: colouring must preserve every character`);
  // Only the known token spans may appear; everything else is escaped text.
  const leftovers = html.replace(/<span class="tk-[a-z]">/g, "").replace(/<\/span>/g, "");
  assert.doesNotMatch(leftovers, /[<>]/, `${label}: no raw markup may leak into the editor`);
  const opened = (html.match(/<span /g) || []).length;
  const closed = (html.match(/<\/span>/g) || []).length;
  assert.equal(opened, closed, `${label}: spans must be balanced`);
  return html;
}
function tokens(html, type) {
  return [...html.matchAll(new RegExp(`<span class="tk-${type}">([\\s\\S]*?)</span>`, "g"))].map(
    (match) => plain(match[1]),
  );
}

// ------------------------------------------------------------------ language lookup
assert.deepEqual(languageForPath("src/app.py"), { id: "python", name: "Python", extension: "py" });
assert.equal(languageForPath("index.HTML").id, "markup");
assert.equal(languageForPath("a/b/styles.scss").name, "SCSS");
assert.equal(languageForPath("Main.java").name, "Java");
assert.equal(languageForPath("notes").id, "plain");
assert.equal(languageForPath("archive.tar.gz").id, "plain");
assert.equal(languageForPath("").name, "Plain Text");
assert.equal(languageForPath(undefined).id, "plain");

// Every extension the workspace accepts has a language.
const developerTools = fs.readFileSync(
  new URL("../public/developer-tools.js", import.meta.url),
  "utf8",
);
const worker = fs.readFileSync(
  new URL("../weronika-py/weronika_agent/workspace.py", import.meta.url),
  "utf8",
);
const allowed = /ALLOWED_EXTENSIONS = \{([^}]*)\}/.exec(worker);
assert.ok(allowed, "worker workspace must declare its allowed extensions");
const extensions = [...allowed[1].matchAll(/"\.([a-z0-9]+)"/g)].map((match) => match[1]);
assert.ok(extensions.length >= 40);
for (const extension of extensions) {
  const language = languageForPath(`file.${extension}`);
  assert.notEqual(language.name, "", `.${extension} needs a display name`);
  if (extension !== "txt")
    assert.notEqual(language.id, "plain", `.${extension} should be coloured`);
  assertFaithful(
    `x = 1 // "a" <b> & 'c' # d\n\t/* e */ <!-- f -->\n`,
    language.id,
    `.${extension}`,
  );
}
assert.match(
  developerTools,
  /workspace-syntax\.js/,
  "the workspace editor must use the syntax module",
);

// ------------------------------------------------------------------ escaping
assert.equal(
  escapeHtml(`<script>alert("x") && 1 > 0</script>`),
  `&lt;script&gt;alert("x") &amp;&amp; 1 &gt; 0&lt;/script&gt;`,
);
assert.equal(
  highlightCode("<img src=x onerror=alert(1)>", "plain"),
  "&lt;img src=x onerror=alert(1)&gt;",
);
assert.equal(highlightCode("a < b", "unknown-language"), "a &lt; b");
assert.equal(highlightCode("", "python"), "");
assert.equal(highlightCode(null, "python"), "");
for (const language of [
  "javascript",
  "python",
  "markup",
  "css",
  "json",
  "markdown",
  "config",
  "shell",
  "sql",
]) {
  assertFaithful(
    `</span><script>alert(1)</script>&amp;<span class="tk-k">`,
    language,
    `${language} injection`,
  );
}

// ------------------------------------------------------------------ JavaScript
{
  const source = [
    `import { run } from "./run.js";`,
    `// greet the user`,
    `const PATTERN = /^[a-z/]+$/gi;`,
    `export async function greet(name = 'you') {`,
    `  const half = total / 2 / count;`,
    "  return `Hello ${name}` + String(0x1f) + 3.5e2;",
    `}`,
    `/* block`,
    `   comment */`,
    `class Robot extends Machine { @bound arm() { return this.joints.map(fix); } }`,
  ].join("\n");
  const html = assertFaithful(source, "javascript");
  const keywords = tokens(html, "k");
  for (const keyword of [
    "import",
    "from",
    "const",
    "export",
    "async",
    "function",
    "return",
    "class",
    "extends",
    "this",
  ]) {
    assert.ok(keywords.includes(keyword), `"${keyword}" should be a keyword`);
  }
  assert.deepEqual(tokens(html, "c"), ["// greet the user", "/* block\n   comment */"]);
  assert.deepEqual(
    tokens(html, "r"),
    ["/^[a-z/]+$/gi"],
    "a regex literal is one token; division is not a regex",
  );
  const strings = tokens(html, "s");
  assert.ok(strings.includes(`"./run.js"`));
  assert.ok(strings.includes(`'you'`));
  assert.ok(strings.includes("`Hello ${name}`"));
  assert.deepEqual(tokens(html, "n"), ["2", "0x1f", "3.5e2"]);
  const functions = tokens(html, "f");
  for (const name of ["greet", "String", "arm", "map"])
    assert.ok(functions.includes(name), `${name}() is a call`);
  assert.ok(tokens(html, "t").includes("Robot"));
  assert.ok(tokens(html, "t").includes("Machine"));
  assert.ok(tokens(html, "a").includes("joints"));
  assert.ok(tokens(html, "v").includes("@bound"));
  assert.ok(tokens(html, "b").includes("PATTERN"));
}
// A keyword inside a string or comment stays part of that string or comment.
{
  const html = assertFaithful(`const a = "return if"; // const b = 1`, "javascript");
  assert.deepEqual(tokens(html, "k"), ["const"]);
}
// Unterminated strings and comments colour to the end of the line or file without failing.
assertFaithful(`const a = "open\nconst b = 2;`, "javascript");
assertFaithful("const a = `open\nstill open", "javascript");
assertFaithful(`/* never closed\ncode()`, "javascript");
assertFaithful(`let x = "ends with backslash\\`, "javascript");
assertFaithful(`x = a / b; y = /unterminated`, "javascript");

// ------------------------------------------------------------------ TypeScript
{
  const html = assertFaithful(
    `interface Point { readonly x: number }\ntype Id = string | null;`,
    "typescript",
  );
  for (const keyword of ["interface", "readonly", "number", "type", "string"]) {
    assert.ok(tokens(html, "k").includes(keyword), `"${keyword}" should be a TypeScript keyword`);
  }
  assert.ok(tokens(html, "b").includes("null"));
}

// ------------------------------------------------------------------ Python
{
  const source = [
    `# -*- coding: utf-8 -*-`,
    `"""Module doc`,
    `spanning lines."""`,
    `import os`,
    `@dataclass`,
    `class Arm(Base):`,
    `    def reach(self, target: float = 1_000.5) -> None:`,
    `        label = f"reach #{target}"  # not a comment inside the string`,
    `        if target is None or not self.ready:`,
    `            return print('नमस्ते', len(label))`,
  ].join("\n");
  const html = assertFaithful(source, "python");
  for (const keyword of ["import", "class", "def", "if", "is", "or", "not", "return"]) {
    assert.ok(tokens(html, "k").includes(keyword), `"${keyword}" should be a Python keyword`);
  }
  assert.deepEqual(tokens(html, "c"), [
    "# -*- coding: utf-8 -*-",
    "# not a comment inside the string",
  ]);
  assert.ok(
    tokens(html, "s").includes(`"""Module doc\nspanning lines."""`),
    "a docstring is one string token",
  );
  assert.ok(tokens(html, "s").includes(`"reach #{target}"`));
  assert.ok(tokens(html, "s").includes(`'नमस्ते'`));
  assert.ok(tokens(html, "v").includes("@dataclass"));
  assert.ok(tokens(html, "n").includes("1_000.5"));
  assert.ok(tokens(html, "b").includes("None"));
  assert.ok(tokens(html, "b").includes("self"));
  assert.ok(tokens(html, "f").includes("reach"));
  assert.ok(tokens(html, "f").includes("print"));
  assert.ok(tokens(html, "t").includes("Arm"));
}

// ------------------------------------------------------------------ HTML with embedded CSS and JS
{
  const source = [
    `<!doctype html>`,
    `<!-- page -->`,
    `<html lang="en">`,
    `<head><style>body { color: #0af; margin: 0 auto; }</style></head>`,
    `<body class='x' hidden>`,
    `  <p>Tom &amp; Jerry: 1 < 2</p>`,
    `  <script>const n = 1; if (n < 2) { console.log("</p>"); }</script>`,
    `  <br/>`,
    `</body></html>`,
  ].join("\n");
  const html = assertFaithful(source, "markup");
  const tags = tokens(html, "t");
  for (const tag of ["doctype", "html", "head", "style", "body", "p", "script", "br"]) {
    assert.ok(tags.includes(tag), `<${tag}> should be a tag`);
  }
  assert.deepEqual(tokens(html, "c"), ["<!-- page -->"]);
  const attributes = tokens(html, "a");
  for (const name of ["lang", "class", "hidden", "color", "margin"])
    assert.ok(attributes.includes(name));
  assert.ok(tokens(html, "s").includes(`"en"`));
  assert.ok(tokens(html, "s").includes(`'x'`));
  assert.ok(tokens(html, "s").includes(`"</p>"`), "script content is coloured as JavaScript");
  assert.ok(tokens(html, "k").includes("const"));
  assert.ok(tokens(html, "n").includes("#0af"), "style content is coloured as CSS");
  assert.ok(tokens(html, "b").includes("&amp;"));
}
assertFaithful(`<div class="open`, "markup", "unterminated attribute");
assertFaithful(`<script>let a = 1;`, "markup", "unterminated script");
assertFaithful(`a < b and <<< >>> </ <1> <>`, "markup", "stray angle brackets");
assertFaithful(
  `<template><div :class="{a: b}" @click="go">{{ msg }}</div></template>`,
  "markup",
  "vue",
);

// ------------------------------------------------------------------ CSS
{
  const source = [
    `/* theme */`,
    `@media (max-width: 600px) {`,
    `  .card:hover > a[href^="http"] { color: rgba(0, 170, 255, .5) !important; --glow: 12px; }`,
    `}`,
    `#app { font: 12px/1.4 "Fira Code", monospace; background: url(x.png) }`,
  ].join("\n");
  const html = assertFaithful(source, "css");
  assert.deepEqual(tokens(html, "c"), ["/* theme */"]);
  assert.ok(tokens(html, "k").includes("@media"));
  assert.ok(tokens(html, "k").includes("!important"));
  const properties = tokens(html, "a");
  for (const property of ["color", "font", "background"]) assert.ok(properties.includes(property));
  assert.ok(tokens(html, "v").includes("--glow"));
  assert.ok(tokens(html, "f").includes("rgba"));
  assert.ok(tokens(html, "f").includes("url"));
  assert.ok(tokens(html, "n").includes("12px"));
  assert.ok(tokens(html, "s").includes(`"Fira Code"`));
  assert.ok(
    tokens(html, "t").some((selector) => selector.includes(".card:hover")),
    "selectors are coloured as a unit",
  );
}
assertFaithful(`a { color: red`, "css", "unterminated rule");
assertFaithful(
  `.a { .b { color: red; &:hover { x: y } } }\n$gap: 4px;\n// scss comment`,
  "css",
  "scss nesting",
);

// ------------------------------------------------------------------ JSON
{
  const html = assertFaithful(
    `{"name": "arm", "joints": [1, -2.5e3, true, null], "nested": {"a:b": "c: d"}}`,
    "json",
  );
  assert.deepEqual(tokens(html, "a"), [`"name"`, `"joints"`, `"nested"`, `"a:b"`]);
  assert.deepEqual(tokens(html, "s"), [`"arm"`, `"c: d"`]);
  assert.deepEqual(tokens(html, "n"), ["1", "-2.5e3"]);
  assert.deepEqual(tokens(html, "b"), ["true", "null"]);
}
assertFaithful(`{"a": "unterminated`, "json");

// ------------------------------------------------------------------ Markdown and config
{
  const html = assertFaithful(
    "# Title\n\nSome **bold**, *italic*, `code` and [a link](https://example.com).\n\n- item\n1. first\n> quote\n\n```js\nconst a = 1;\n```\n",
    "markdown",
  );
  assert.deepEqual(tokens(html, "h"), ["# Title"]);
  assert.deepEqual(tokens(html, "e"), ["**bold**"]);
  assert.deepEqual(tokens(html, "i"), ["*italic*"]);
  assert.ok(tokens(html, "s").includes("`code`"));
  assert.ok(tokens(html, "s").includes("const a = 1;"), "fenced code is set apart");
  assert.deepEqual(tokens(html, "t"), ["[a link]"]);
  assert.deepEqual(tokens(html, "a"), ["(https://example.com)"]);
  assert.deepEqual(tokens(html, "c"), ["> quote"]);
}
{
  const html = assertFaithful(
    `# settings\n[tool.app]\nname = "weronika"\nport: 8765 # local\nenabled: true\n- item: 'x'\n`,
    "config",
  );
  assert.deepEqual(tokens(html, "t"), ["[tool.app]"]);
  assert.deepEqual(tokens(html, "a"), ["name", "port", "enabled", "item"]);
  assert.ok(tokens(html, "c").includes("# settings"));
  assert.ok(tokens(html, "c").includes("# local"));
  assert.ok(tokens(html, "n").includes("8765"));
  assert.ok(tokens(html, "b").includes("true"));
}

// ------------------------------------------------------------------ other languages
{
  const html = assertFaithful(
    `#!/bin/bash\nNAME="x"; echo "$NAME" ${"${HOME}"} $# # trailing\nif [ -f a ]; then exit 1; fi`,
    "shell",
  );
  assert.ok(tokens(html, "c").includes("#!/bin/bash"));
  assert.ok(tokens(html, "c").includes("# trailing"));
  assert.ok(tokens(html, "v").includes("${HOME}"));
  assert.ok(tokens(html, "k").includes("if"));
  assert.ok(tokens(html, "k").includes("fi"));
}
{
  const html = assertFaithful(
    `SELECT id, name FROM users WHERE age >= 18 -- adults\n  AND name LIKE 'A%';`,
    "sql",
  );
  for (const keyword of ["SELECT", "FROM", "WHERE", "AND", "LIKE"])
    assert.ok(tokens(html, "k").includes(keyword));
  assert.deepEqual(tokens(html, "c"), ["-- adults"]);
  assert.deepEqual(tokens(html, "s"), [`'A%'`]);
}
{
  const html = assertFaithful(
    `#include <stdio.h>\nint main(void) { printf("hi\\n"); return 0; }`,
    "c",
  );
  assert.ok(tokens(html, "k").includes("#include"));
  assert.ok(tokens(html, "k").includes("int"));
  assert.ok(tokens(html, "f").includes("main"));
}
assertFaithful(
  `fn main() { let v: Vec<i32> = vec![1, 2]; println!("{:?}", v); } // 'a lifetime`,
  "rust",
);
assertFaithful(`package main\nfunc main() { s := \`raw\nstring\`; fmt.Println(s) }`, "go");
assertFaithful(`<?php echo "$name {$a['b']}"; # c\n?>`, "php");
assertFaithful(`--[[ block ]] local t = { 1, 2 } -- line`, "lua");
assertFaithful(`<# block #> Write-Host "$env:USERPROFILE" # c`, "powershell");
assertFaithful(`@echo off\n:: comment\nset "A=1"\nif exist a.txt echo yes`, "batch");

// ------------------------------------------------------------------ robustness
const odd = [
  "",
  "\n",
  "\n\n\n",
  "\t \t",
  "\r\n\r\n",
  "\\",
  '"',
  "'",
  "`",
  "/",
  "//",
  "/*",
  "<",
  "<!--",
  "&",
  "#",
  "@",
  "$",
  "${",
  "0x",
  "1.2.3.4e",
  "😀 = '🚀'  // 表情",
  "x".repeat(5000),
  "(".repeat(400) + ")".repeat(400),
  "\u0000\u0001\u2028\u2029\ufeff",
  "a\u00a0b\u3000c",
];
const everyLanguage = [
  "plain",
  "javascript",
  "typescript",
  "python",
  "markup",
  "css",
  "json",
  "markdown",
  "config",
  "java",
  "c",
  "cpp",
  "csharp",
  "go",
  "rust",
  "kotlin",
  "swift",
  "dart",
  "php",
  "scala",
  "ruby",
  "shell",
  "powershell",
  "batch",
  "sql",
  "lua",
  "r",
  "perl",
  "elixir",
  "graphql",
  "proto",
];
for (const language of everyLanguage) {
  for (const text of odd)
    assertFaithful(text, language, `${language} edge ${JSON.stringify(text.slice(0, 12))}`);
}

// Deterministic pseudo-random text: the round trip must hold for arbitrary input.
let seed = 20261111;
const random = () => {
  seed = (seed * 1103515245 + 12345) & 0x7fffffff;
  return seed / 0x7fffffff;
};
const alphabet = [
  ..."abcXYZ019_$ \n\t\"'`/\\*#<>&=:;,.(){}[]!@%-+|^~?",
  "//",
  "/*",
  "*/",
  "<!--",
  "-->",
  '"""',
  "'''",
  "${",
  "</script>",
  "<style>",
  "<script>",
  "function",
  "return",
  "def",
  "class",
  "--",
  "::",
  "<#",
  "#>",
  "é",
  "न",
  "😀",
];
for (let round = 0; round < 400; round += 1) {
  let text = "";
  const length = Math.floor(random() * 90);
  for (let index = 0; index < length; index += 1)
    text += alphabet[Math.floor(random() * alphabet.length)];
  const language = everyLanguage[round % everyLanguage.length];
  assertFaithful(text, language, `${language} random #${round}`);
}

// Large inputs stay responsive: colouring is linear, and huge files fall back to plain text.
{
  const big = "const value = compute(alpha, 'beta', 42); // note\n".repeat(3000);
  assert.ok(big.length < HIGHLIGHT_LIMIT);
  const started = Date.now();
  assertFaithful(big, "javascript", "large javascript");
  assertFaithful(
    '<div class="row"><span>cell &amp; more</span></div>\n'.repeat(3000),
    "markup",
    "large markup",
  );
  assertFaithful(".rule { color: #fff; margin: 0 auto; }\n".repeat(3000), "css", "large css");
  assert.ok(Date.now() - started < 4000, "colouring 150 KB files must stay fast");

  const huge = "x = 1 < 2\n".repeat(HIGHLIGHT_LIMIT / 10 + 1);
  assert.ok(huge.length > HIGHLIGHT_LIMIT);
  const html = highlightCode(huge, "python");
  assert.doesNotMatch(html, /<span/, "files past the limit are shown without colouring");
  assert.equal(plain(html), huge);
}
// Pathological inputs must not blow up on backtracking.
{
  const started = Date.now();
  assertFaithful("/".repeat(20000), "javascript", "slashes");
  assertFaithful("<".repeat(20000), "markup", "angle brackets");
  assertFaithful('"'.repeat(20001), "python", "quotes");
  assertFaithful("*".repeat(20000), "markdown", "asterisks");
  assertFaithful("a:".repeat(10000), "css", "colons");
  assertFaithful("{".repeat(20000), "css", "braces");
  assertFaithful("[".repeat(20000) + "\n", "config", "brackets");
  assertFaithful(("_a ".repeat(60) + "\n").repeat(100), "markdown", "underscores");
  assert.ok(Date.now() - started < 4000, "pathological input must not hang the editor");
}

console.log("workspace syntax colouring checks passed");
