# ios-q: commands, settings, state

`scripts/ios-q` is a single bash file (macOS's own bash 3.2 is enough). It needs nothing installed beyond Xcode's command-line tools. `ios-q help` prints the summary.

## Commands

| Command | What it does |
|---|---|
| `take <lane> --who W --why T [--max 30m] [--udid U] [--wait 10m] [--pid P]` | Waits for a place in the lane and prints its place every minute. Then it prints `export IOS_Q_LEASE=…` (and `EXPO_CUSTOM_BUILD_ROOT` for `build`) and exits. The lease stays until `release`, the end of `--max`, or the end of the holder process. |
| `run <lane> --who W --why T [--max …] [--udid U] -- <command…>` | Takes the lane, runs the command, and releases on exit, error, Ctrl-C or SIGTERM. The exit code is the command's own (130 or 143 when interrupted). Here `--max` is a hard limit: the command is stopped when it runs out. |
| `sim <project> --who W --why T [--max 60m] [--no-boot] [--wait …]` | Lends a booted simulator of the project's pool and a Metro port. It prints `export IOS_Q_UDID=… IOS_Q_PORT=… IOS_Q_LEASE=… IOS_Q_SIM_NAME=…` for `eval`. If none is free, it boots the next simulator of the pool (within the boot lane and the booted ceiling) unless `--no-boot`, and otherwise waits. |
| `release [<lease> \| <lane>] [--who W] [--any-holder]` | With a lease id, releases that lease. Otherwise it releases the caller's own leases (those whose holder is the caller's agent process), on one lane or on all. `--any-holder --who W` releases W's leases from anywhere; it's for the orchestrator, cleaning up after an agent. |
| `status [--json]` | Load, free memory, booted count, every lease (lane, who, held/max, pid, why, simulator and port), every waiter in order, and the priorities. |
| `who [<lane>]` | Who holds a lane, one per line, or `free`. |
| `prioritize <who> [--for 60m]` / `unprioritize <who>` | Marks that the user is waiting on `<who>`. Its takes go to the front, skip the load gate and may boot a 4th simulator. The orchestrator calls this; agents never do (`--user-waiting` on a take is refused on purpose). |
| `reap` | Releases leases whose holder is gone or whose `--max` ran out. Every call does this anyway, and every waiter does it on every poll. |

`--who` is the agent's card or ticket code; it's how people read the queue. `--why` is one line: "dev client fp=ab12", "smoke en", "push check on the phone".

Exit codes: 0 granted (for `run`, the command's own code), 2 usage, 3 gave up after `--wait`, 4 no simulator for that project, 5 a simulator would not boot.

## Lanes

| Lane | Width | Load gate (× cores) | Memory floor | Default `--max` |
|---|---|---|---|---|
| `build` | 1 | 2 | yes | 60m |
| `boot` | 1, with at most 3 booted (4 for a prioritized agent) | 2 | yes | 10m |
| `maestro` | 2, 1 per udid | 4 | yes | 25m |
| `heavy` | 1 | 2 | yes | 60m |
| `device` | 1 | none | no | 30m |
| simulator lease (`sim`) | one per simulator | none (booting uses `boot`'s) | no | 60m |

The queue is first come, first served within a lane, with prioritized agents ahead of everyone else. A waiter that can't run because its simulator is busy doesn't hold up the waiters behind it. Admission is checked for the whole lane, so while the load is high nobody in that lane starts, and the line keeps its order.

A Maestro run needs its simulator free. Another agent's `maestro` lease on that udid blocks it, and so does a `sim` lease held by someone else. Your own `sim` lease does not block your own run: the match is on the same `--who` or the same holder process.

## Who holds a lease

`take` and `sim` record the first ancestor of the caller that is not a shell or wrapper (`sh`, `bash`, `zsh`, `env`, `timeout`, `nohup`, …). For a coding agent's Bash tool, that is the agent process itself, so the lease lasts as long as the agent and ends when it does, even if the agent never calls `release`. `run` records itself. The process start time is stored too, so a pid that gets reused after the holder dies doesn't keep the lease alive. `--pid P` (or `IOS_Q_HOLDER_PID`) overrides this, for a script that wants its own pid to be the holder.

## Settings

Set them in the environment, or as `IOS_Q_*=value` lines in `~/.config/ios-q/config` (or the file `IOS_Q_CONFIG` names). The environment wins over the file.

| Setting | Default | Meaning |
|---|---|---|
| `IOS_Q_STATE` | `~/.local/state/ios-q` | where leases, waiters, priorities and the log live |
| `IOS_Q_WIDTH_<LANE>` | 1, 1, 2, 1, 1 | lane widths (`BUILD`, `BOOT`, `MAESTRO`, `HEAVY`, `DEVICE`) |
| `IOS_Q_LOAD_<LANE>` | 2, 2, 4, 2 | load gate as a multiple of `hw.ncpu` (`BUILD`, `BOOT`, `MAESTRO`, `HEAVY`) |
| `IOS_Q_MIN_FREE_GB` | 4 | memory floor (free + inactive + speculative + purgeable pages) |
| `IOS_Q_BOOTED_MAX` / `IOS_Q_BOOTED_MAX_PRIORITY` | 3 / 4 | booted-simulator ceiling (about 4 GB each) |
| `IOS_Q_SIM_MATCH` | `exact` | `exact`: the pool is `<Project>` and `<Project> B`, `<Project> C`…; `prefix`: any simulator named `<Project> …` |
| `IOS_Q_METRO_BASE` | 8081 | ports are handed out from base + 1, skipping ports already listening |
| `IOS_Q_JOBS` | 8 | `-jobs` added to a bare `xcodebuild` under `run build` |
| `IOS_Q_POLITE` | 1 | 0 to skip `taskpolicy -c utility` |
| `IOS_Q_CCACHE_CONFIGPATH` | — | exported as `CCACHE_CONFIGPATH` to builds (see build-caches.md) |
| `IOS_Q_PRIORITY_FOR` | 60m | how long `prioritize` lasts by default |
| `IOS_Q_POLL` / `IOS_Q_REPORT_EVERY` | 3 / 60 | seconds between tries, and between "your place" lines |
| `IOS_Q_LEGACY_LOCK` | — | an older `mkdir` lock directory the build lane also holds (below) |
| `IOS_Q_SIMCTL` | `xcrun simctl` | a different simctl (tests use a fake one) |

Test hooks, which the test suite uses in place of real readings: `IOS_Q_TEST_LOAD`, `IOS_Q_TEST_LOAD_FILE`, `IOS_Q_TEST_FREE_MB`, `IOS_Q_TEST_FREE_MB_FILE`, `IOS_Q_TEST_NCPU`, `IOS_Q_TEST_NO_PORT_CHECK`.

## State

```
~/.local/state/ios-q/
  leases/<lane>.<id>        key=value: who why pid pstart since until udid port project root
  waiters/<seq>.<id>        key=value: lane who why pid since udid seq
  priority/<who>            the epoch second the priority ends
  seq  log  .mutex/
```

Every change happens inside a short `mkdir` mutex. A mutex left behind by a dead process is broken at once, and any mutex older than 30 s is broken too. The log keeps the last few thousand grants, releases and reaps. Read it to learn why a phase sat idle.

## Living next to an older lock

Agents that are already running may still call an older script that takes a `mkdir` lock (say `/tmp/my-ios.lock`, with a `who` file inside). To make both count together:

1. Set `IOS_Q_LEGACY_LOCK=/tmp/my-ios.lock` in `~/.config/ios-q/config`. A build lease then also creates that directory and writes `who` into it, so the old script waits behind ios-q. A directory ios-q didn't create counts as a held build slot, so ios-q waits behind the old script. ios-q clears a directory it didn't create after 45 minutes, which is the old script's own stale rule. While its own build lease lives, it refreshes the directory's time, so an old waiter never clears it.
2. Replace the old script with a shim, using an atomic `mv` so that a running copy keeps its old file:

```bash
#!/bin/bash
# old-lock.sh: now a shim onto ios-q's build lane.
Q=${IOS_Q:-ios-q}
export IOS_Q_LEGACY_LOCK=${IOS_Q_LEGACY_LOCK:-/tmp/my-ios.lock}
case "${1:-}" in
  take) "$Q" take build --who "${2:-unknown}" --why "via old-lock.sh" --max 45m >/dev/null || exit $?
        echo "lock taken by ${2:-unknown}" ;;
  release) "$Q" release build --legacy; echo "lock released" ;;
  who) "$Q" who build ;;
  *) echo "usage: old-lock.sh take <who> | release | who" >&2; exit 2 ;;
esac
```

`release --legacy` releases the caller's own build lease. If the caller holds none, it removes a lock directory ios-q didn't create, which is what an agent that took the old lock before the swap expects. Once no agent uses the old name, delete the shim and the setting.

## Going further

A shell script can only learn that a holder ended when someone calls it. An orchestrator that already knows when each agent exits can do better: release at once, show the queue in its own window ("P5 · waiting for build behind P2, 14 min"), raise a wait longer than ten minutes, and expose `prioritize` as a verb of its own. Keep the same lanes, widths and admission rules, so agents' briefs don't change.
