#!/usr/bin/env node
// Phone-width screenshots and an overflow report for a list of pages, through a real
// headless Chrome driven over the DevTools protocol. No dependencies (Node 22+ for the
// built-in WebSocket). Run it from the project's root. See ../SKILL.md for the workflow.
//
//   node mobile-shots.mjs [--config mobile-shots.json] [--base http://localhost:3001]
//     [--out mobile-shots] [--label before] [--profile <dir>]
//     [--login admin@example.com --next /admin] [--mail-tag <project>] [--mailpit http://127.0.0.1:8025]
//     [--cookie name=value]... [--width 390 --height 844] [--full] [--desktop] [--strict]
//     /path "/path|click=Button text|wait=1500" ...
//
// Steps after the path, separated by "|": click=<visible text> (first button/link/tab whose
// text starts with it), wait=<ms>, scroll=<px>, eval=<js expression, no "|" inside>.
// With no paths given, it shoots the `pages` of the settings file.
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { basename, delimiter, join } from "node:path";

if (typeof WebSocket === "undefined") {
  console.error("mobile-shots needs Node 22 or later (for the built-in WebSocket)");
  process.exit(2);
}

const args = process.argv.slice(2);
const opt = (name) => {
  const i = args.indexOf(`--${name}`);
  if (i === -1) return undefined;
  const v = args[i + 1];
  if (v === undefined || v.startsWith("--")) fail(`--${name} needs a value`);
  args.splice(i, 2);
  return v;
};
const opts = (name) => {
  const out = [];
  for (let v = opt(name); v !== undefined; v = opt(name)) out.push(v);
  return out;
};
const flag = (name) => {
  const i = args.indexOf(`--${name}`);
  if (i === -1) return false;
  args.splice(i, 1);
  return true;
};
function fail(message) {
  console.error(message);
  process.exit(2);
}

// The project's settings, so a run needs no flags: where the app runs, how to sign in to it,
// which pages to shoot. Flags override them.
const configPath = opt("config");
const config = readJson(configPath ?? "mobile-shots.json", configPath !== undefined) ?? {};
const loginConfig = config.login ?? {};

const [base, baseFrom] = pick(
  [opt("base"), "--base"],
  [config.base, "mobile-shots.json"],
  [process.env.BETTER_AUTH_URL ?? readEnvFile("BETTER_AUTH_URL"), "BETTER_AUTH_URL"],
  ["http://localhost:3000", "default"],
);
const out = opt("out") ?? config.out ?? "mobile-shots";
const label = opt("label") ?? "";
const login = opt("login");
const next = opt("next") ?? loginConfig.next ?? "/";
const mailTag = opt("mail-tag") ?? config.mailTag ?? packageSlug();
const mailpit = (opt("mailpit") ?? config.mailpit ?? "http://127.0.0.1:8025").replace(/\/$/, "");
const cookies = opts("cookie");
const full = flag("full");
const desktop = flag("desktop");
const strict = flag("strict");
const width = Number(opt("width") ?? (desktop ? 1280 : 390));
const height = Number(opt("height") ?? (desktop ? 800 : 844));
// Outside the project, so its session cookies never end up in a commit, and one per project,
// so two projects can be audited at once.
const profile = opt("profile") ?? config.profile ?? join(tmpdir(), `mobile-shots-${basename(process.cwd())}-${hash(process.cwd())}`);

// The sign-in flow of --login: a magic link requested through the app and read from the
// shared Mailpit. The defaults are Better Auth's magic-link plugin; the settings file
// changes them for an app that requests its links some other way.
const LOGIN_PATH = loginConfig.path ?? "/api/auth/sign-in/magic-link";
const LOGIN_BODY = loginConfig.body ?? { email: "{email}", callbackURL: "{next}" };
const LINK_RE = new RegExp(loginConfig.link ?? "magic-link/verify");
const MAIL_WAIT_MS = 30_000;

const unknown = args.find((a) => a.startsWith("--"));
if (unknown) fail(`unknown option ${unknown}`);
const urls = args.length > 0 ? args : (config.pages ?? []);
if (urls.length === 0) fail("no pages given, on the command line or as `pages` in mobile-shots.json");
if (login && !mailTag) fail("--login needs the project's mail tag: --mail-tag, or `mailTag` in mobile-shots.json");

const dir = join(out, [label, width, desktop && "desktop"].filter(Boolean).join("-"));
mkdirSync(dir, { recursive: true });

function pick(...candidates) {
  return candidates.find(([value]) => value);
}

function hash(text) {
  return createHash("sha1").update(text).digest("hex").slice(0, 8);
}

function readJson(file, required) {
  if (!existsSync(file)) {
    if (required) fail(`no settings file at ${file}`);
    return null;
  }
  try {
    return JSON.parse(readFileSync(file, "utf8"));
  } catch (e) {
    fail(`${file}: ${e.message}`);
  }
}

// A variable from the project's .env files, the way the dev server would see it.
function readEnvFile(name) {
  for (const file of [".env.local", ".env"]) {
    if (!existsSync(file)) continue;
    const m = readFileSync(file, "utf8").match(new RegExp(`^\\s*(?:export\\s+)?${name}\\s*=\\s*(.*)$`, "m"));
    const value = m?.[1].replace(/\s+#.*$/, "").trim().replace(/^(["'])(.*)\1$/, "$2");
    if (value) return value;
  }
  return undefined;
}

// Development mail is tagged with the project's slug (X-Tags), which is usually its
// package name.
function packageSlug() {
  try {
    return JSON.parse(readFileSync("package.json", "utf8")).name?.replace(/^@[^/]+\//, "");
  } catch {
    return undefined;
  }
}

function findChrome() {
  if (process.env.CHROME) return process.env.CHROME;
  const apps = {
    darwin: [
      "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
      "/Applications/Chromium.app/Contents/MacOS/Chromium",
      "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
      "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    ],
    win32: [
      `${process.env.PROGRAMFILES}\\Google\\Chrome\\Application\\chrome.exe`,
      `${process.env["PROGRAMFILES(X86)"]}\\Microsoft\\Edge\\Application\\msedge.exe`,
    ],
  }[process.platform];
  if (apps) return apps.find((path) => existsSync(path));
  const names = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge"];
  const path = (process.env.PATH ?? "").split(delimiter);
  for (const name of names) if (path.some((p) => existsSync(join(p, name)))) return name;
  return undefined;
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let chrome;

// Chrome picks a free debugging port and writes it into the profile, so two runs (two
// projects) never fight over one.
async function startChrome() {
  const bin = findChrome();
  if (!bin) fail("no Chrome found: set CHROME to the browser's executable");
  const portFile = join(profile, "DevToolsActivePort");
  rmSync(portFile, { force: true });
  chrome = spawn(
    bin,
    [
      "--headless=new",
      "--remote-debugging-port=0",
      `--user-data-dir=${profile}`,
      "--no-first-run",
      "--no-default-browser-check",
      "--hide-scrollbars",
      `--window-size=${width},${height}`,
    ],
    { stdio: "ignore" },
  );
  chrome.on("error", (e) => fail(`could not start ${bin}: ${e.message}`));
  for (let i = 0; i < 75 && chrome.exitCode === null; i++) {
    if (existsSync(portFile)) {
      const [port, path] = readFileSync(portFile, "utf8").split("\n");
      if (port && path) return `ws://127.0.0.1:${port}${path}`;
    }
    await sleep(200);
  }
  throw new Error(`chrome did not start (is another run using the profile ${profile}?)`);
}

class CDP {
  constructor(ws) {
    this.ws = ws;
    this.id = 0;
    this.pending = new Map();
    this.listeners = new Map();
    ws.addEventListener("message", (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.id !== undefined) {
        const p = this.pending.get(msg.id);
        if (!p) return;
        this.pending.delete(msg.id);
        if (msg.error) p.reject(new Error(msg.error.message));
        else p.resolve(msg.result);
      } else if (msg.method) {
        const key = `${msg.sessionId ?? ""}:${msg.method}`;
        for (const fn of this.listeners.get(key) ?? []) fn(msg.params);
      }
    });
  }
  send(method, params = {}, sessionId) {
    const id = ++this.id;
    this.ws.send(JSON.stringify({ id, method, params, sessionId }));
    return new Promise((resolve, reject) => this.pending.set(id, { resolve, reject }));
  }
  on(sessionId, method, fn) {
    const key = `${sessionId ?? ""}:${method}`;
    if (!this.listeners.has(key)) this.listeners.set(key, []);
    this.listeners.get(key).push(fn);
  }
  once(sessionId, method) {
    return new Promise((resolve) => {
      const key = `${sessionId ?? ""}:${method}`;
      const fn = (params) => {
        const arr = this.listeners.get(key);
        arr.splice(arr.indexOf(fn), 1);
        resolve(params);
      };
      this.on(sessionId, method, fn);
    });
  }
}

// Runs in the page: every element past the right edge of the viewport ("spills") or whose
// text is wider than its own box ("text"), and on phones every text field under 16px, which
// iOS Safari zooms into on focus ("zoom"). Elements inside a sideways-scrolling container
// show up as spills too; the page-level scrollWidth is the number that must match vw.
const OVERFLOW_SCRIPT = `(() => {
  const vw = document.documentElement.clientWidth;
  const sw = document.documentElement.scrollWidth;
  const describe = (el) => {
    const cls = typeof el.className === 'string' ? '.' + el.className.split(' ').filter(Boolean).slice(0, 6).join('.') : '';
    return el.tagName.toLowerCase() + cls + ' "' + (el.textContent.trim() || el.getAttribute('placeholder') || el.name || '').slice(0, 40) + '"';
  };
  const bad = [];
  const seen = new Set();
  for (const el of document.querySelectorAll('body *')) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) continue;
    const cs = getComputedStyle(el);
    const spills = r.right > vw + 1;
    const textOverflow = el.scrollWidth > el.clientWidth + 1 && cs.overflowX === 'visible' && el.children.length === 0 && el.textContent.trim().length > 0;
    if (spills || textOverflow) {
      const desc = describe(el);
      if (seen.has(desc)) continue;
      seen.add(desc);
      bad.push({ desc, right: Math.round(r.right), width: Math.round(r.width), scrollWidth: el.scrollWidth, clientWidth: el.clientWidth, why: spills ? 'spills' : 'text' });
    }
  }
  const zoom = [];
  if (${!desktop}) {
    const fields = 'input:not([type=checkbox],[type=radio],[type=range],[type=color],[type=file],[type=hidden],[type=submit],[type=button],[type=reset],[type=image]), textarea, select, [contenteditable=""], [contenteditable=true]';
    for (const el of document.querySelectorAll(fields)) {
      const r = el.getBoundingClientRect();
      const size = parseFloat(getComputedStyle(el).fontSize);
      if ((r.width > 0 || r.height > 0) && size < 16) zoom.push({ desc: describe(el), fontSize: size, why: 'zoom' });
    }
  }
  const viewport = document.querySelector('meta[name=viewport]')?.content ?? null;
  return JSON.stringify({ vw, sw, viewport, bad: bad.slice(0, 30), zoom: zoom.slice(0, 10), docHeight: document.documentElement.scrollHeight });
})()`;

// Fills "{email}" and "{next}" anywhere in the request body of the settings.
function fillBody(value, vars) {
  if (typeof value === "string") return value.replace(/\{(email|next)\}/g, (_, k) => vars[k]);
  if (Array.isArray(value)) return value.map((v) => fillBody(v, vars));
  if (value && typeof value === "object") return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, fillBody(v, vars)]));
  return value;
}

// The newest mail tagged with this project and sent to [email] after [since]. Mailpit is
// shared by every project on the machine, hence the tag, and keeps old links, hence the time:
// a mail sent by a background worker can arrive after an older, already used one.
async function waitForMail(email, since) {
  const query = encodeURIComponent(`tag:"${mailTag}" to:"${email}"`);
  const deadline = Date.now() + MAIL_WAIT_MS;
  while (Date.now() < deadline) {
    let list;
    try {
      list = await (await fetch(`${mailpit}/api/v1/search?query=${query}&limit=10`)).json();
    } catch {
      throw new Error(`Mailpit does not answer at ${mailpit} (brew services start mailpit)`);
    }
    const msg = list.messages?.find(
      (m) => Date.parse(m.Created) >= since - 1000 && m.To.some((t) => t.Address.toLowerCase() === email.toLowerCase()),
    );
    if (msg) return await (await fetch(`${mailpit}/api/v1/message/${msg.ID}`)).json();
    await sleep(500);
  }
  throw new Error(
    `no mail tagged "${mailTag}" to ${email} in ${MAIL_WAIT_MS / 1000}s. Is the address allowed to sign in, ` +
      `and does the dev server tag its mail with X-Tags: ${mailTag}? (--mail-tag or mailTag in mobile-shots.json)`,
  );
}

// The first link in the mail (HTML hrefs, then plain-text URLs) that matches the settings.
function findLink(detail) {
  const hrefs = [...(detail.HTML ?? "").matchAll(/href="([^"]+)"/g)].map((m) => m[1].replace(/&amp;/g, "&"));
  const urls = [...(detail.Text ?? "").matchAll(/https?:\/\/[^\s<>"')]+/g)].map((m) => m[0]);
  return [...hrefs, ...urls].find((u) => LINK_RE.test(u));
}

async function main() {
  try {
    await fetch(base, { redirect: "manual" });
  } catch {
    throw new Error(`nothing answers at ${base} (from ${baseFrom}); start the dev server or pass --base`);
  }
  console.log(`base ${base} (${baseFrom})\nshots ${dir}\nprofile ${profile}\nviewport ${width}x${height}${desktop ? " desktop" : " phone"}`);

  const ws = new WebSocket(await startChrome());
  await new Promise((r) => ws.addEventListener("open", r));
  const cdp = new CDP(ws);

  const { targetId } = await cdp.send("Target.createTarget", { url: "about:blank" });
  const { sessionId } = await cdp.send("Target.attachToTarget", { targetId, flatten: true });
  const s = (method, params) => cdp.send(method, params, sessionId);

  await s("Page.enable");
  await s("Runtime.enable");
  await s("Network.enable");
  if (!desktop) {
    await s("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 2, mobile: true });
    await s("Emulation.setTouchEmulationEnabled", { enabled: true, maxTouchPoints: 5 });
    await s("Network.setUserAgentOverride", {
      userAgent:
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1",
    });
  } else {
    await s("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 2, mobile: false });
  }

  for (const cookie of cookies) {
    const [name, ...rest] = cookie.split("=");
    await s("Network.setCookie", { name, value: rest.join("="), url: base });
  }

  async function navigate(url, settle = 1500) {
    const loaded = cdp.once(sessionId, "Page.loadEventFired");
    await s("Page.navigate", { url });
    await Promise.race([loaded, sleep(15000)]);
    await sleep(settle);
  }

  async function evaluate(expression) {
    const r = await s("Runtime.evaluate", { expression, returnByValue: true });
    return r.result.value;
  }

  async function clickText(text) {
    const expr = `(() => {
      const els = [...document.querySelectorAll('button, a, [role="tab"], [role="menuitem"], label, summary')];
      const el = els.find((e) => e.textContent.trim().toLowerCase().startsWith(${JSON.stringify(text.toLowerCase())}));
      if (!el) return 'NOT FOUND: ' + ${JSON.stringify(text)};
      el.scrollIntoView({ block: 'center' });
      el.click();
      return 'clicked ' + el.tagName + ' ' + el.textContent.trim().slice(0, 40);
    })()`;
    console.log("   ", await evaluate(expr));
    await sleep(1200);
  }

  if (login) {
    const since = Date.now();
    const res = await fetch(new URL(LOGIN_PATH, base), {
      method: "POST",
      headers: { "content-type": "application/json", origin: new URL(base).origin },
      body: JSON.stringify(fillBody(LOGIN_BODY, { email: login, next })),
    });
    if (!res.ok) throw new Error(`sign-in request ${res.status} ${(await res.text()).slice(0, 300)}`);
    console.log(`waiting for the sign-in mail (tag:${mailTag} to:${login})`);
    const link = findLink(await waitForMail(login, since));
    if (!link) throw new Error(`no link matching /${LINK_RE.source}/ in the mail (login.link in mobile-shots.json)`);
    // The session cookie has to land on the origin the pages are shot from: a link built for
    // another host (127.0.0.1, a Tailscale address) is opened on --base instead.
    const url = new URL(link);
    const origin = new URL(base);
    if (url.origin !== origin.origin) {
      console.log(`the link points at ${url.origin}; opening it on ${origin.origin}`);
      url.protocol = origin.protocol;
      url.host = origin.host;
    }
    console.log("signing in via", url.href.slice(0, 80));
    await navigate(url.href, 2500);
    const landed = await evaluate("location.href");
    console.log("now at", landed);
    if (new URL(landed).searchParams.has("error")) throw new Error(`the sign-in link was refused: ${landed}`);
  }

  const report = [];
  let overflowing = 0;
  let zooming = 0;
  let lastViewport;
  for (const u of urls) {
    const [path, ...steps] = u.split("|");
    const url = path.startsWith("http") ? path : new URL(path, base).href;
    await navigate(url);
    for (const step of steps) {
      const [kind, value] = step.split(/=(.*)/s);
      if (kind === "click") await clickText(value);
      else if (kind === "scroll") await evaluate(`window.scrollTo(0, ${Number(value)})`);
      else if (kind === "wait") await sleep(Number(value));
      else if (kind === "eval") console.log("   ", await evaluate(value));
      else console.log(`    unknown step "${step}"`);
    }
    const href = await evaluate("location.href");
    const ov = JSON.parse(await evaluate(OVERFLOW_SCRIPT));
    const name = u.replace(/^https?:\/\/[^/]+/, "").replace(/[^a-z0-9]+/gi, "_").replace(/^_|_$/g, "").slice(0, 70) || "root";
    const shot = await s("Page.captureScreenshot", {
      format: "png",
      captureBeyondViewport: full,
      clip: full ? { x: 0, y: 0, width, height: Math.min(ov.docHeight, 6000), scale: 1 } : undefined,
    });
    const file = join(dir, `${name}.png`);
    writeFileSync(file, Buffer.from(shot.data, "base64"));
    report.push({ url: u, href, file, ...ov });
    if (ov.sw > ov.vw) overflowing++;
    if (ov.zoom.length) zooming++;
    if (ov.viewport !== lastViewport) console.log(`\nviewport meta: ${ov.viewport ?? "MISSING"}`);
    lastViewport = ov.viewport;
    console.log(`\n== ${u}  →  ${href}\n   file ${file}\n   viewport ${ov.vw} scrollWidth ${ov.sw}${ov.sw > ov.vw ? "  <-- WIDER THAN THE SCREEN" : ""} height ${ov.docHeight}`);
    for (const b of ov.bad) console.log(`   ${b.why.padEnd(6)} right=${b.right} w=${b.width} sw=${b.scrollWidth}/${b.clientWidth}  ${b.desc}`);
    for (const z of ov.zoom) console.log(`   zoom   font-size=${z.fontSize}px  ${z.desc}`);
  }
  writeFileSync(join(dir, "report.json"), JSON.stringify(report, null, 2));
  console.log(`\n${report.length} pages, ${overflowing} wider than the screen${desktop ? "" : `, ${zooming} with fields under 16px`}`);
  // Closed rather than killed, so the profile writes the session cookie to disk for the next run.
  cdp.send("Browser.close").catch(() => {});
  for (let i = 0; i < 25 && chrome.exitCode === null && chrome.signalCode === null; i++) await sleep(200);
  ws.close();
  chrome.kill();
  if (strict && (overflowing || zooming)) process.exit(1);
}

process.on("SIGINT", () => {
  chrome?.kill();
  process.exit(130);
});

main().catch((e) => {
  console.error(e.message ?? e);
  chrome?.kill();
  process.exit(1);
});
