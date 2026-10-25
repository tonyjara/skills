# The Mac

The coordinator runs this once per Sunday, before the projects. Nothing here needs the user,
except macOS updates and anything that would quit an app the user has open.

## 1. Inventory

```bash
sw_vers -productVersion; softwareupdate --list 2>&1 | tail -n +3
node -v; which -a node; pnpm -v; npm -v; bun -v
pnpm ls -g --depth 0; npm ls -g --depth 0
claude --version; codex --version; gh --version | head -1; stripe --version
brew outdated --verbose; brew outdated --cask --greedy --verbose
ls /Applications/Postgres.app/Contents/Versions
```

Node on this Mac comes from pnpm's global store (`pnpm add -g node@<v>`, linked as
`~/Library/pnpm/bin/node`), not Homebrew, nvm or fnm. Postgres.app ships its own Postgres,
OrbStack runs Docker, Flutter comes from fvm (`~/fvm`).

## 2. Update

- **Homebrew**: `brew update && brew upgrade` (formulae). Casks: `brew upgrade --cask` for the
  ones not open right now; list the rest for the user. Then `brew cleanup`.
- **Node**: the patched release of the line in use (brief), e.g. `pnpm add -g node@24.x.y`,
  then `node -v`. Keep the major unless the brief says the line is EOL.
- **Global JS tools**: `pnpm update -g` (pnpm, npm, vercel…), then `npm ls -g` for any
  npm-global leftovers (`npm update -g`). Check each against the brief's IOC block first.
- **Infrastructure tools** (Tailscale, gh, Stripe CLI, Claude Code, Codex, OrbStack and the
  rest): one at a time, as in section 3.
- **Flutter**: `fvm releases`, then `fvm install <v>` / `fvm global <v>` only if the brief
  has a Flutter or Dart fix; projects pin their own version. Switch only when `ps` shows no
  `flutter`/`fvm` build running, then `flutter doctor`. 2026-10-25: global 3.41.6 → 3.47.8.
- **macOS**: report pending updates and Rapid Security Responses; the user installs them
  (they restart the Mac).

## 3. Infrastructure tools

The tools that hold credentials or open network paths. Every Sunday, put each one's installed
version next to the latest in the brief's "Infrastructure versions" table and update it. Do
these one at a time and check each before the next.

| Tool | Installed by | Update | Watch out |
|---|---|---|---|
| **Homebrew** itself | its installer | `brew update` (updates brew and the formula list), then `brew --version` | Run before every other brew step |
| **Tailscale** | `Tailscale.app`, standalone build (not the App Store) | The app's own updater (menu bar → Update), or the latest pkg from tailscale.com | Updating drops this Mac off the tailnet for a few seconds, so ssh to the VPS, the direct Postgres port and the panel go with it. Do it when no agent is working on a host or running migrations, then check `tailscale status` and `ssh -o BatchMode=yes nytojara-vps true` |
| **OpenSSH** | macOS (`/usr/bin/ssh`) | Only with macOS updates | Report the version; nothing to do between OS updates |
| **gh** | brew | `brew upgrade gh` | All four accounts stay logged in (`gh auth status`); never `gh auth switch` while other agents run |
| **Stripe CLI** | brew (`stripe/stripe-cli/stripe`) | `brew upgrade stripe` | `stripe --version`; its login expires every 90 days, the user renews it |
| **Claude Code** | native installer (`~/.local/bin/claude` → `~/.local/share/claude/versions/`) | `claude update` | Running sessions keep their version until restarted; say so, do not restart them |
| **Codex** | standalone (`~/.codex/packages/standalone/`) | `codex update`, or its installer again | Same as Claude Code |
| **OrbStack** (Docker on the Mac) | brew cask | `brew upgrade --cask orbstack` | Restarts the local Docker engine and every local container: ask if anything local is running |
| **cloudflared** | brew | `brew upgrade cloudflared` | Restart any tunnel that runs from this Mac |
| **1Password CLI** (`op`) | brew cask | `brew upgrade --cask 1password-cli` | |
| **Vercel CLI** | pnpm global | `pnpm add -g vercel@latest` | |
| **osv-scanner** | brew | `brew install osv-scanner` / `brew upgrade osv-scanner` | Needed by every project agent |

Anything new that holds a token, opens a tunnel or reaches a server goes in this table.

## 4. Report

Versions before → after, what was left and why, in the "Mac" section of the Sunday summary.
