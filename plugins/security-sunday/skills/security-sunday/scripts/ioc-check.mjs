#!/usr/bin/env node
// Looks for known-bad packages in every lockfile under a repo.
//
//   node ioc-check.mjs <repo-dir> <ioc-file> [<ioc-file> ...]
//
// Each <ioc-file>: one entry per line, `name@version` (an exact bad release) or `name` alone
// (any version is bad). Blank lines and lines starting with # are ignored. The brief's IOC
// block is in this format.
//
// Reads pnpm-lock.yaml, package-lock.json, npm-shrinkwrap.json, bun.lock and yarn.lock
// as text; installs nothing and runs no package code. Exit 0 clean, 1 hit, 2 usage error.

import { lstatSync, readFileSync, readdirSync } from "node:fs";
import { join, relative } from "node:path";

const [repo, ...iocFiles] = process.argv.slice(2);
if (!repo || !iocFiles.length) {
  console.error("usage: node ioc-check.mjs <repo-dir> <ioc-file> [<ioc-file> ...]");
  process.exit(2);
}

const iocs = iocFiles
  .flatMap((f) => readFileSync(f, "utf8").split("\n"))
  .map((l) => l.replace(/#.*/, "").trim())
  .filter(Boolean)
  .map((l) => {
    const at = l.lastIndexOf("@");
    return at > 0 ? { name: l.slice(0, at), version: l.slice(at + 1) } : { name: l, version: null };
  });

const LOCKFILES = new Set(["pnpm-lock.yaml", "package-lock.json", "npm-shrinkwrap.json", "bun.lock", "yarn.lock"]);
const SKIP = new Set(["node_modules", ".git", ".next", "dist", "build", ".turbo", ".worktrees"]);

function* lockfiles(dir) {
  for (const entry of readdirSync(dir)) {
    if (SKIP.has(entry)) continue;
    const p = join(dir, entry);
    const st = lstatSync(p, { throwIfNoEntry: false }); // symlinked dirs (iOS .symlinks) are skipped
    if (!st) continue;
    if (st.isDirectory()) yield* lockfiles(p);
    else if (LOCKFILES.has(entry)) yield p;
  }
}

// Every (name, version) a lockfile resolves, whatever its format.
function resolved(file, text) {
  const out = [];
  if (file.endsWith(".json")) {
    const data = JSON.parse(text);
    for (const [key, v] of Object.entries(data.packages ?? {})) {
      const name = v.name ?? key.split("node_modules/").pop();
      if (name && v.version) out.push([name, v.version]);
    }
    const walk = (deps) => {
      for (const [name, v] of Object.entries(deps ?? {})) {
        if (v.version) out.push([name, v.version]);
        walk(v.dependencies);
      }
    };
    walk(data.dependencies); // lockfileVersion 1
  } else if (file.endsWith("yarn.lock")) {
    let names = [];
    for (const line of text.split("\n")) {
      if (/^\S/.test(line) && line.trim().endsWith(":")) {
        names = line.slice(0, -1).split(",").map((s) => s.trim().replace(/^"|"$/g, "").replace(/@(npm:)?[^@]*$/, ""));
      } else {
        const m = line.match(/^\s+version:?\s+"?([^"\s]+)"?/);
        if (m) for (const n of names) out.push([n, m[1]]);
      }
    }
  } else {
    // pnpm-lock.yaml and bun.lock both spell resolutions as name@version.
    const re = /(?:^|[\s'"/(,\[])((?:@[\w.-]+\/)?[\w.-]+)@(\d+\.\d+\.\d+[\w.+-]*)/gm;
    for (const m of text.matchAll(re)) out.push([m[1], m[2]]);
  }
  return out;
}

const byName = new Map();
for (const ioc of iocs) byName.set(ioc.name, [...(byName.get(ioc.name) ?? []), ioc]);

let hits = 0;
let files = 0;
for (const file of lockfiles(repo)) {
  files++;
  const pairs = resolved(file, readFileSync(file, "utf8"));
  const seen = new Set();
  for (const [name, version] of pairs) {
    for (const ioc of byName.get(name) ?? []) {
      if (ioc.version && version !== ioc.version) continue;
      const key = `${name}@${version}`;
      if (seen.has(key)) continue;
      seen.add(key);
      hits++;
      console.log(`HIT ${relative(repo, file)}: ${key}${ioc.version ? "" : " (package listed as bad at any version)"}`);
    }
  }
}

console.log(`${files} lockfile(s), ${iocs.length} IOC(s), ${hits} hit(s)`);
process.exit(hits ? 1 : 0);
