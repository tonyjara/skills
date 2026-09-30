# skills

Skills for Claude Code and Codex. Each skill is a folder with a `SKILL.md`,
grouped into plugins so the whole repo works as a Claude Code plugin
marketplace.

## Use them

**Claude Code**

```
/plugin marketplace add tonyjara/skills
/plugin install coding@tonyjara-skills
```

**Codex, or by hand.** Copy (or symlink) a skill folder into
`~/.codex/skills/` or `~/.claude/skills/`:

```sh
git clone https://github.com/tonyjara/skills
ln -s "$PWD/skills/plugins/coding/skills/best-coding-practices" ~/.claude/skills/
```

## What's here

| plugin | skill | what it does |
|---|---|---|
| `coding` | `best-coding-practices` | Read first, match the codebase, keep diffs small, verify before claiming done. |

## Layout

```
.claude-plugin/marketplace.json     the list of plugins in this repo
plugins/<plugin>/
  .claude-plugin/plugin.json
  skills/<skill>/
    SKILL.md                        frontmatter (name, description) + instructions
    references/                     loaded only when SKILL.md points to it
```

To add a skill, create `plugins/<plugin>/skills/<name>/SKILL.md`. To add a
plugin, also add an entry to `marketplace.json`.
