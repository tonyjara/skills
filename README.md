# skills

Skills for Claude Code and Codex. Each skill is its own plugin, so you install
one at a time and never get a bundle you did not ask for.

## Use them

**Claude Code.** Add the marketplace once, then install each skill you want:

```
/plugin marketplace add tonyjara/skills
/plugin install best-coding-practices@tonyjara-skills
/plugin install auth-like-tony@tonyjara-skills
/plugin install image-cropper@tonyjara-skills
/plugin install mobile-web@tonyjara-skills
/plugin install security-sunday@tonyjara-skills
/plugin install agent-sessions@tonyjara-skills
/plugin install expo-ios-agents@tonyjara-skills
/plugin install iracing-livery@tonyjara-skills
/plugin install build-in-public@tonyjara-skills
```

**Codex, or by hand.** Copy (or symlink) a skill folder into
`~/.codex/skills/` or `~/.claude/skills/`:

```sh
git clone https://github.com/tonyjara/skills
ln -s "$PWD/skills/plugins/auth-like-tony/skills/auth-like-tony" ~/.claude/skills/
```

## What's here

| skill | what it does |
|---|---|
| `best-coding-practices` | Read first, match the codebase, keep diffs small, verify before claiming done. |
| `auth-like-tony` | Admin sign-in with Better Auth magic links, an `ADMIN_EMAIL` allowlist, nodemailer over SMTP, one shared Mailpit for every local project, `requireAdmin()` everywhere. |
| `image-cropper` | Image upload field: compress in the browser, crop at a fixed aspect with zoom-out-to-fit, re-editable crops, min-width gate, wide + square preview. |
| `mobile-web` | Phone-ready web UI: locked viewport scale, no iOS zoom on fields, safe areas, bottom-sheet dialogs, scrolling tab rows, tables as cards, and a screenshot + overflow audit at phone width. |
| `security-sunday` | Weekly patch run: a dated CVE brief, then per project audit, patch/minor updates, Node bumps, checks, one commit, deploy check and a security log; the VPS and Mac procedures, an inventory of every project and host, and a Sunday report. |
| `agent-sessions` | Agents check an app's admin or signed-in pages in production: a separate agent user, an hour's session minted in the database from inside the container (or, for apps on Vercel, by a SQL function in the database's container and a one-time key the app signs), read-only unless asked, an audit table, revoke, and an ssh helper that hands the cookie to Playwright or curl without printing it. Better Auth, Supabase, Auth.js. |
| `expo-ios-agents` | Expo / React Native iOS with several coding agents on one Mac: the `ios-q` lane queue (build, boot, maestro, heavy, device) with a place in line, a user-is-waiting priority, leases that end with their holder and refusal under load; one dev client per native fingerprint with JS through Metro; a leased pool of always-booted simulators; Jest first, Maestro as a small smoke set; the iPhone via `devicectl`; build caches across worktrees; a weekly disk sweep. |
| `iracing-livery` | iRacing paints (car, `car_spec`, helmet, suit) from a brand's design language: get the car's template and map its UV panels, the orientation traps (trunk text, the sideways hood, mirrored sides), helmet visor clearance and the seam, spec channels, file names with the customer ID and their folders, Ctrl+R outside the pit stall, the sim's number panels left alone, flat previews on the wireframe, the in-sim screenshot loop, and a brand's posters as a full wrap that still looks like a race car; scripts to map, draw, export, make spec maps and preview. |
| `build-in-public` | Post ideas from what was shipped: kururu cards, commits and reports for a day or a week, across every project or only the ones named, ranked into 5 to 8 nuggets spread across projects, filtered for clients, people, production data and security, drafted for X, Bluesky, LinkedIn and YouTube, filed as unscheduled Platypost drafts, and a numbered list that fits a phone. The owner's asset and client names live in a local config, not in the skill. |

## Skill or plugin?

A **skill** is a folder with a `SKILL.md`: instructions Claude loads when a task
matches its description, plus any reference files it points to. A **plugin** is
the package Claude Code installs; it can carry skills, commands, agents and
hooks. Here every plugin carries exactly one skill and has the skill's name, so
"install a plugin" and "install a skill" mean the same thing.

## Layout

```
.claude-plugin/marketplace.json     the list of plugins in this repo
plugins/<name>/
  .claude-plugin/plugin.json        name, description, version
  skills/<name>/
    SKILL.md                        frontmatter (name, description) + instructions
    references/                     loaded only when SKILL.md points to it
    scripts/                        run by Claude, from the skill's folder
```

To add a skill, create `plugins/<name>/skills/<name>/SKILL.md` and
`plugins/<name>/.claude-plugin/plugin.json`, add an entry to
`marketplace.json`, and a row to the table above. One skill per plugin.
