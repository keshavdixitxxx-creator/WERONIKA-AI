#!/usr/bin/env node
/**
 * Copies the canonical UI from public/ into weronika-py/ so the Python local
 * agent ships exactly the same Weronika as the web app.
 *
 * Usage: npm run sync:standalone
 */
import { copyFileSync, mkdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const source = join(root, "public");
const target = join(root, "weronika-py");

const STATIC_FILES = [
  "weronika.html",
  "weronika-workspace.js",
  "weronika-commands.js",
  "weronika-local-prompts.js",
  "weronika-media-intent.js",
  "technical-models.js",
  "technical-viewer.js",
  "weronika-google.js",
  "weronika-memory.js",
  "weronika-same-browser.js",
  "weronika-automation.js",
  "favicon.ico",
  "robots.txt",
];

mkdirSync(join(target, "public"), { recursive: true });

for (const file of STATIC_FILES) {
  const from = join(source, file);
  const to = join(target, "public", file);
  copyFileSync(from, to);
  const kb = (statSync(to).size / 1024).toFixed(0);
  console.log(`  public/${file} -> weronika-py/public/${file} (${kb} KB)`);
}

// The portable single-file copy the agent falls back to.
copyFileSync(join(source, "weronika.html"), join(target, "weronika.html"));
console.log("  public/weronika.html -> weronika-py/weronika.html");

const html = readFileSync(join(source, "weronika.html"), "utf8");
console.log(
  `\nSynced. UI is ${(html.length / 1024).toFixed(0)} KB, ${html.split("\n").length} lines.`,
);
