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
