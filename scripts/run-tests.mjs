#!/usr/bin/env node
/** Runs every tests/*.mjs check in its own process and reports a summary. */
import { readdirSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const dir = join(root, "tests");
const files = readdirSync(dir)
  .filter((f) => f.endsWith(".mjs"))
  .sort();

let failed = 0;
for (const file of files) {
  const result = spawnSync(process.execPath, [join(dir, file)], { stdio: "inherit" });
  if (result.status !== 0) {
    failed += 1;
    console.error(`✗ ${file}`);
  } else {
    console.log(`✓ ${file}`);
  }
}

console.log(`\n${files.length - failed}/${files.length} JS suites passed`);
process.exit(failed === 0 ? 0 : 1);
