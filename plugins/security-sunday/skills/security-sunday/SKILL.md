---
name: security-sunday
description: Weekly security and update run ("security sunday") for every project, host and the Mac. Writes or reads a dated CVE brief, then for one project per agent detects the stack, audits (pnpm/npm/bun audit, osv-scanner, lockfile checks for compromised npm packages), applies every patch and minor update and only the majors a CVE needs, bumps the Node runtime in .nvmrc, engines, Dockerfiles, CI, Vercel or Dokploy when a fix needs it, runs install, typecheck, lint, tests and build, commits once, pushes by the project's own rules, checks the production deploy came up healthy and appends to docs/security/log.md. Also has the procedure for the VPS and other hosts (hosts.md), the Mac (mac.md), the inventory of projects, repos, gh accounts and deploy targets (inventory.yaml) and the Sunday report template. Load it whenever someone says security sunday, patch, update all packages, dependency updates, CVE, vulnerability, npm audit, outdated, supply chain, compromised package, upgrade Node, or keep the server or the Mac up to date.
---

# Security Sunday

Every Sunday: find out what was disclosed, then bring every project, host and the Mac up to
date, and end with one report. The skill grows each week: whatever was missing or wrong this
time goes back into these files (see "Improving the skill").

The source lives in `~/Desktop/Nyto/skills/plugins/security-sunday/skills/security-sunday/`
(repo `tonyjara/skills`). The installed plugin is a read-only copy: read from either, edit
only the checkout.

| File | What it is |
|---|---|
| `inventory.yaml` | Every project and host: path, repo, gh account, push rules, stack, Node pins, deploy target, health URL, checks |
| `briefs/<date>.md` | That Sunday's advisories and what they mean for us. Read the newest one first |
| `hosts.md` | The VPS and any future server: inventory, OS and Docker updates, what needs the user's OK |
| `mac.md` | Homebrew, global npm tools, Node, the CLIs |
| `report-template.md` | The per-project report and the Sunday summary |
| `briefs/<date>-iocs.txt` | That Sunday's known-bad npm packages, one `name@version` (or bare `name`) per line |
| `scripts/ioc-check.mjs` | Finds IOC entries in every lockfile of a repo (pnpm, npm, bun, yarn), installs nothing |
| `scripts/newest.mjs` | Newest version of each package in its own major, and the newest one past the 48-hour release age |
| `scripts/ioc-fetch.sh` | Builds an IOC list from GitHub's npm malware advisories since a date, plus named GHSAs |

## Who does what

- **The coordinator** (the first card of the Sunday) writes the brief (below), runs `mac.md`
  and `hosts.md`, starts one agent per project in `inventory.yaml`, then merges their reports
  into the Sunday summary, applies their inventory changes and commits this repo.
- **A project agent** runs "Updating one project" for exactly one project and reports back.
  It does not edit this skill or the inventory: it puts those changes in its report.
  Its card says: *"Security Sunday <date>: run the security-sunday skill for <project>."*

## Writing the brief

`briefs/<YYYY-MM-DD>.md`, from the previous brief forward (never more than ~5 weeks back).
Use your own web search first; `kururu_web` only if it fails. Every finding gets a date, a
link, the severity, the fixed version and "affects us: where / no". Sources, each time:

- Node: `nodejs.org/en/blog/vulnerability`, and which lines are still supported.
- npm ecosystem: GitHub advisories for the deps in the inventory (`key_deps`), the Next.js and
  Vercel changelogs, and supply-chain news (Socket, Aikido, StepSecurity, Wiz) for compromised
  packages: put their `name@version` pairs in `briefs/<date>-iocs.txt` (curated, committed).
  Then build the full feed for this Mac's agents (large, not committed):
  `scripts/ioc-fetch.sh <last brief date> <GHSA ids of hijacked real packages> >
  ~/.cache/security-sunday/<date>-gh-malware.txt` (a few minutes).
- Servers: PostgreSQL security page, Ubuntu USNs for noble, Docker / containerd / runc,
  Traefik and Dokploy GitHub advisories, OpenSSH release notes, Tailscale security bulletins.
- Mac: Apple security releases, Claude Code, Codex, gh, Stripe CLI release notes.

Include an **"Infrastructure versions"** table: every tool in `mac.md` section 3 and
`hosts.md` section 4 (Tailscale on each machine, OpenSSH, Docker, Dokploy, Traefik, gh,
Homebrew, Stripe CLI, Claude Code, Codex…), installed → latest, and whether an advisory makes it
urgent. These get updated every Sunday like packages, not only when a CVE names them.

Open the brief with **"Do this week"**: the short list every agent must check, most urgent first.

## Updating one project

Read your entry in `inventory.yaml` and the newest brief first, then the project's own
`CLAUDE.md` / `AGENTS.md`. **The project's rules win over this skill** (push policy, "no git
commands", migration rules). Not in the inventory yet: add it to your report (see the end of
`inventory.yaml`) and keep going.

### 1. Start clean

- `git status`: on the default branch, clean, `git pull --ff-only`.
- Not clean, or another branch checked out (someone else is working there): never stash, reset
  or commit their work. Work in a worktree instead: `git fetch && git worktree add
  <scratchpad>/<name>-security-sunday-<date> origin/<branch> -b security-sunday/<date>`, copy
  the gitignored `.env*` files the build needs into it, and `git worktree remove --force` it
  when done. (Not `../<name>.worktrees/`: the safety check will not let an agent remove that
  empty parent afterwards.)
- **A long-lived branch the inventory lists under `branches`** (work not ready for production)
  gets the same updates in its own worktree: its `package.json` takes the default branch's
  versions (keeping only its own extra entries), `pnpm-workspace.yaml` and
  `docs/security/log.md` are copied as they are, the lockfile starts from the default branch's
  and `pnpm install` adds the branch's extras. Identical files merge cleanly when the branch
  comes back. Push the branch; never merge it. In a `pr-only` repo that merges PRs with merge
  commits, merge the security branch into the long-lived branch instead (manifests take the
  PR's versions, the lockfile is the PR's plus `pnpm install`): a later commit on the PR then
  cannot conflict, and merging the default branch in after the PR lands is clean.
- gh account: never `gh auth switch` (other agents share it). Per command:
  `GH_TOKEN=$(gh auth token -u <gh_account>) gh …`, and the same prefix on `git push` for an
  `https://` remote (git's credential helper is `gh`). `git@` remotes push with the Mac's SSH key.

### 2. Detect the stack

Lockfile → manager: `pnpm-lock.yaml` pnpm, `package-lock.json` npm, `bun.lock` bun,
`yarn.lock` yarn. Two lockfiles: the one `packageManager` names (or the CI uses) is real;
report the other, do not delete it unasked. Then look for `pubspec.yaml` (Flutter, often in
`mobile/`), `go.mod`, `pyproject.toml` / `requirements*.txt`, `Package.swift`.
Use the manager the project pins (`packageManager`): `corepack` or pnpm's own version switch
picks it; never rewrite a lockfile with another manager or major.
The Mac's global pnpm is 12: a pin it cannot start ("no @pnpm/exe.darwin-arm64 native binary")
is usually a half-fetched copy (an interrupted switch): move
`~/Library/pnpm/package-manager-store/v11/links/@pnpm/exe/<version>` aside and run `pnpm -v`
again. Until then `npx -y pnpm@<pin>` runs the pinned version. With npm 11,
`npm view <pkg> time --json` returns an array: read `[0]`.

### 3. Audit, before changing anything

```bash
pnpm audit                             # or: npm audit / bun audit
osv-scanner scan source -r .           # every lockfile kind, incl. pubspec.lock, go.sum (brew install osv-scanner)
node <skill>/scripts/ioc-check.mjs . <skill>/briefs/<date>-iocs.txt ~/.cache/security-sunday/<date>-gh-malware.txt
```

Also look for worm droppings: hooks you do not recognise in `.claude/settings*.json` or
`.vscode/tasks.json`, and files named in the brief (this month: `setup.mjs`, `Math_Symbol.js`,
`math_init.js` outside `node_modules`).

Keep the counts (critical / high / moderate) for the log. An IOC hit is an incident, not an
update: stop, tell the user, and do not run install or any script in that repo.

The audits only know GitHub's global database. An advisory published in the package's own repo
(better-auth GHSA-965c-763c-88jm, React GHSA-xqc2-xf4c-x3h3 on 2026-10-25) is missed by both:
check every brief entry that names one of your deps against the lockfile by hand
(`gh api repos/<owner>/<repo>/security-advisories/<GHSA id>` gives the affected ranges).

### 4. Update

- **Patch and minor: all of them.** `pnpm update -r` (within ranges), then `pnpm outdated -r`
  for pinned versions and bump each to the newest of its own major. Keep each specifier's
  style: exact stays exact, `^` stays `^`. npm: `npm update` + `npm outdated`; bun:
  `bun update` + `bun outdated`. `pnpm update -r` rewrites major-only ranges (`^4` becomes
  `^4.3.3`): put them back. Folders outside the workspace that get copied (a `templates/`
  scaffold) are never updated: bump their pins by hand to match the apps. Where every pin is
  exact, `pnpm update` changes nothing direct: `node <skill>/scripts/newest.mjs name@current …`
  lists the version to take (`pnpm outdated --format json` mixes `[WARN]` lines into stdout).
- **Vendored copies keep their old version strings.** Next 16.4.3 bundles React as
  `19.3.0-canary-…` with the 19.3.1 fix inside: check for the fixed code, not the version.
- **Majors** only when a CVE is fixed only in the new major, or when the change is trivial
  (no breaking notes that touch our code, all checks pass). Everything else goes in the report
  under "majors left", with one line on what it would take. Read the peer ranges first
  (`npm view <pkg>@<v> peerDependencies`): a wrapper often caps the major (typescript-eslint 8.72
  allows TypeScript < 6.1, trpc-to-openapi 3.3 wants zod-openapi ^5), and that is "blocked
  upstream", not work left.
- **Transitive CVE with no fixed parent:** an override (`overrides` in `pnpm-workspace.yaml` or
  `pnpm.overrides`; npm `overrides`) to the fixed version, with a comment naming the CVE. Remove
  overrides that are no longer needed. A parent that is unmaintained but never loads the
  vulnerable package can get a scoped override (`"<parent>>esbuild": ^0.25.12`).
- **Read the audit's paths after updating.** `pnpm update` keeps a transitive version its
  parent's range still allows (fast-uri 3.1.7 under ajv) and a peer it once auto-installed
  (next 16.3.5 under better-auth, an optional peer). A temporary override, `pnpm install`,
  remove it, `pnpm install` again moves the first and drops the second, with no override left.
- pnpm before 11.28.8 reads `--config.<key>=<number>` as a string (it crashes or idles), so
  put numeric settings in `pnpm-workspace.yaml`. When every agent installs at once the registry
  is slow: add `fetchTimeout: 600000` there for the run and take it out before committing.
  To wait on an install, wait on your own process id: `pgrep -f "pnpm update"` also matches
  other agents' runs.
- **Two-day release age, permanent.** Every project refuses versions published less than 48
  hours ago (compromised releases are usually pulled within a day). Add it if it is missing,
  set it explicitly even where the manager has a default (pnpm 11 defaults to one day), and
  commit it with the updates:

  | Manager | File | Setting | Exempting one fresh CVE fix |
  |---|---|---|---|
  | pnpm ≥10.16 | `pnpm-workspace.yaml` (create it in a single-package repo) | `minimumReleaseAge: 2880` (minutes) | `minimumReleaseAgeExclude: ['next@16.4.3']` |
  | npm ≥11.10 | `.npmrc` | `min-release-age=2` (days) | `min-release-age-exclude=next` |
  | bun ≥1.3 | `bunfig.toml` | `[install]` `minimumReleaseAge = 172800` (seconds) | `minimumReleaseAgeExcludes = ["next"]` |
  | yarn ≥4.10 | `.yarnrc.yml` | `npmMinimalAgeGate: 2880` (minutes) | `npmPreapprovedPackages: ["next"]` |

  Exempt only a CVE fix newer than 48 hours, pinned to that version where the manager allows it,
  with a comment naming the CVE; remove the exemption the next Sunday. Never lower the age. A
  manager or pinned version without the setting (Flutter, Go, Python, an older pnpm): say so in
  the report and apply the rule by hand: skip versions newer than 48 hours.
- **Install scripts:** pnpm 10+ blocks dependency build scripts; do not add a package to
  `onlyBuiltDependencies` / `allowBuilds` without saying why in the report.
- `packageManager`: newest patch/minor of the same major. Vercel installs with that pin (its
  build log: "Detected `pnpm-lock.yaml` version 9 generated by pnpm@11.x from
  package.json#packageManager"); with no pin it picks pnpm from the lockfile's version, which
  can be older than the install-time fixes (10.34.5 / 11.11.0): add the pin. Flutter: `flutter pub upgrade`
  (in constraints); Go: `go get -u=patch ./... && go mod tidy`; Python: the lock tool's upgrade.

### 5. Node runtime, when the brief says a fix needs it

Bump every place the version lives, to the patched release of the same line (or the next LTS
when the line is EOL): `.nvmrc` / `.node-version` / `.tool-versions`, `engines.node` (Vercel
reads its Node major from it, or from the project settings), each Dockerfile `FROM node:…`
(a major-only tag such as `node:24-bookworm-slim` gets the patch on a rebuild with `--pull`;
an exact tag must be edited), `node-version` in `.github/workflows/*`, and Bun's version if pinned.

### 6. Check

`install` → `typecheck` → `lint` → `test` → `build`, using the commands in the inventory
(`checks`). A failure caused by an update: fix it if small, otherwise revert that one package
and list it. When a framework moved (Next, React, Vite, TanStack, Electron) or you are unsure,
start the dev server, load two or three pages (`curl -fsS` or a headless browser), and stop it.
Flutter: `flutter analyze && flutter test`; say whether the change needs a new app build.

An update that migrates a database when it starts (pg-boss minors move its schema; a package's
own migrations) is checked against a scratch database (`createdb <name>_ss_<date>`, migrate,
seed, run, drop it), never the shared dev database the other branches use. Say in the PR what
migrates and what the next agent runs after the merge.

Electron apps: on a slow link electron-builder's download of the Electron zip times out after
10 minutes. Fetch `electron-v<v>-darwin-arm64.zip` and `SHASUMS256.txt` from the GitHub
release yourself (parallel `curl -r` ranges help), check the sha256, and put both in
`~/Library/Caches/electron/<sha256 of "https://github.com/electron/electron/releases/download/v<v>">/`.
To confirm an installed app, launch it once with `--remote-debugging-port=<port>`, read
`navigator.userAgent` and the page text over CDP, then relaunch it plain.

### 7. Commit and push

One commit: `security sunday: YYYY-MM-DD`, body listing the bumps that matter, the CVEs closed
and anything reverted. Push the way the inventory's `push_policy` says:

- `direct`: push the default branch.
- `pr-only`: branch `security-sunday/YYYY-MM-DD`, push it, `gh pr create`, link it in the report.
- `ask`: commit (if the project allows git) and ask the user before pushing.

### 8. Check the deploy

By `deploy.target` in the inventory:

- **vercel**: the deployment for the commit reaches Ready (`gh api
  "repos/<o>/<r>/deployments?sha=<full sha>"`, a short sha matches nothing, + statuses, or
  `vercel ls`), then the production URL and `health` answer 200. `vercel inspect <url> --logs`
  shows the pnpm and Node it used. `vercel link` (needed by `vercel env ls`) pulls a
  `.env.local`: link a scratch folder, never the repo, and delete that file.
- **dokploy**: the GitHub Actions run is green (`gh run watch`), the Swarm service runs the new
  image (`ssh nytojara-vps docker service ps <service> --no-trunc | head -3`), `health` is 200.
- **none / app store / releases**: say what the user has to ship by hand.

A failed deploy: report it with the log lines. Rollbacks on the VPS follow `hosts.md`.

### 9. Log and report

Append to the project's `docs/security/log.md` (create it, with a `# Security log` heading),
in the same commit as the updates when you can:

```markdown
## YYYY-MM-DD — security sunday
- Audit before: 0 critical, 2 high, 5 moderate. After: 0 / 0 / 1 (why it is left).
- Updated: next 16.3.4 → 16.3.7 (CVE-…), 41 others patch/minor.
- Release age: 2880 min (added today / already set). Exemptions: none.
- Node: 24.18.0 → 24.22.x in .nvmrc, Dockerfile, ci.yml.
- Majors left: tailwindcss 4 → 5 (config rewrite).
- Deploy: <url> healthy at HH:MM (commit abc1234). / PR #12.
```

Then fill the project section of `report-template.md` and return it as your final message.

## Improving the skill

Every report ends with "Skill changes": a command that was wrong, a step that was missing, a
project rule the inventory did not know. The coordinator folds them into these files, bumps the
plugin version in `plugin.json`, and commits. Keep each file short and procedural.
