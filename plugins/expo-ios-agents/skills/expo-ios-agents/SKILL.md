---
name: expo-ios-agents
description: Expo / React Native iOS work when several coding agents share one Mac. A lane queue (ios-q) instead of one global lock - build (1), boot (1, at most 3 simulators booted), maestro (2, one per simulator), heavy (1), device (1) - with waiting in line, a user-is-waiting priority, leases that end with their holder, and refusal under high load or low memory. Then one development build per native fingerprint and JS through Metro, a small pool of simulators kept booted and leased (never shut down or erased), Jest first and Maestro as a tagged smoke set, the physical iPhone through devicectl, build caches that work across worktrees, and a weekly disk sweep. Load it before building, installing, booting a simulator, running Maestro or putting a build on a phone for an Expo or React Native iOS app, whenever more than one agent (or an agent and a person) may be doing iOS work on the same Mac, and when someone mentions xcodebuild, expo run:ios, pod install, simctl, Maestro, a dev client, DerivedData, "the build is slow", "the simulator hangs", "build.db disk I/O error", or an iOS lock.
---

# Expo iOS with several agents on one Mac

On one Mac, what slows agents down is not a lack of cores. It's that they all run the most expensive thing at once, at every step:

- every phase starts from a fresh copy, so it pays for a clean native build (10–25 min);
- every phase makes a Release build for its tests, so every JS change runs `xcodebuild`;
- every test run boots a simulator and shuts it down again (4 GB and up to 2 min each time);
- one global lock puts a 20-second flow behind a 20-minute build, and the user waits behind both.

What fixes it, in order of payoff:

1. **One development build per native fingerprint, with JS through Metro.** Most phases never touch Xcode.
2. **Lanes instead of a lock.** Builds, simulators, Maestro and heavy jobs queue separately, and each lane allows a set number at once.
3. **A small pool of simulators, kept booted and leased.**
4. **Build caches that work across copies.**
5. **A weekly disk sweep.**

## Set up once per Mac

```sh
SK=<this skill's folder>
ln -s "$SK/scripts/ios-q" ~/.local/bin/ios-q          # any folder on PATH
ln -s "$SK/scripts/devclient" ~/.local/bin/devclient
mkdir -p ~/.config/ios-q && touch ~/.config/ios-q/config   # IOS_Q_* settings, see references/ios-q.md
```

- **One simulator per project, named after the project.** For example `xcrun simctl create "Acme" "iPhone 17 Pro"`. Make a second one (`"Acme B"`) only if two phases really do test at the same time. A simulator per phase or per agent is the wrong unit.
- **Keep Spotlight out of build output.** Add `~/Library/Developer`, the pnpm store, the projects' `node_modules` and the agents' scratch folders to System Settings → Spotlight → Privacy. Otherwise `mds_stores` re-indexes every build.
- **Turn on ccache and Xcode's compilation cache** ([references/build-caches.md](references/build-caches.md)).

## The lanes

Anything that builds, boots, installs, or drives a simulator or phone goes through `ios-q`. Never run `xcodebuild`, `expo run:ios`, `pod install`, `simctl boot` or `maestro` bare.

| Lane | Width | What takes it |
|---|---|---|
| `build` | 1 | `xcodebuild`, `expo run:ios`, `pod install`, `expo prebuild` |
| `boot` | 1 at a time; at most 3 booted (4 when the user is waiting) | `simctl boot`, done for you by `ios-q sim` |
| `maestro` | 2, and only 1 per simulator | `maestro test`, XCUITest, idb or agent-device sessions |
| `heavy` | 1 | Playwright suites, `docker build`, Jest with more than 4 workers |
| `device` | 1 | anything that uses the iPhone through `devicectl` |

```sh
ios-q run build --who P5 --why "dev client, fp changed" -- npx expo run:ios --no-bundler
ios-q run maestro --who P5 --why "smoke es" -- maestro --udid "$IOS_Q_UDID" test -e LANG=es .maestro
eval "$(ios-q sim acme --who P5 --why "checkout flow")"    # IOS_Q_UDID, IOS_Q_PORT, IOS_Q_LEASE
ios-q status                                               # who holds what, who waits, and why
```

The rules the script enforces:

- **Every take names who is taking it, what for, and for how long** (`--who`, `--why`, `--max`). It blocks until there's a place, and prints its place in line and the reason every minute.
- **`run` takes the lane, runs the command, and always releases**, whether the command succeeds, fails or is interrupted with Ctrl-C. Prefer it to `take` + `release`.
- **A lease ends with its holder.** `take` belongs to the agent's process: the first ancestor that isn't a shell. When that process exits, the next call to `ios-q` frees the lane. `--max` ends a lease that is left open.
- **Admission by load.** `build`, `boot` and `heavy` wait while the 1-minute load average is above 2× the number of cores. `maestro` waits while it is above 4×. Every lane except `device` waits while free memory is under 4 GB. The waiter prints which rule is holding it.
- **Builds run politely.** `run build` starts the command under `taskpolicy -c utility` and sets `EXPO_CUSTOM_BUILD_ROOT` to the caller's copy, so `expo-modules-jsi` builds there and not inside the shared `node_modules` (that clash is the `build.db: disk I/O error`). It adds `-jobs 8` and `COMPILER_INDEX_STORE_ENABLE=NO` to a bare `xcodebuild`. Each copy keeps its own DerivedData: Xcode's default folder is already keyed by the workspace path, so never point two copies at one `-derivedDataPath`. Start Metro with `--max-workers 2`.
- **The user-is-waiting priority belongs to the orchestrator.** When the user is at the phone or watching a simulator, the orchestrator runs `ios-q prioritize <who>`. That agent's takes go to the front of every lane, skip the load gate (the memory floor still applies), and may boot a 4th simulator. An agent never prioritizes itself.

Commands, settings and state: [references/ios-q.md](references/ios-q.md).

## A phase's loop: one dev client, JS through Metro

```sh
npx jest                                          # first, always; no lane needed
eval "$(ios-q sim acme --who P5 --why "phase 5 flows")"
devclient install "$IOS_Q_UDID" || {              # the dev client for this native fingerprint
  ios-q run build --who P5 --why "dev client fp=$(devclient key)" -- \
    npx expo run:ios --device "$IOS_Q_UDID" --no-bundler --output .dev-client
  devclient save .dev-client/*.app                # keep .dev-client/ in .gitignore
}
npx expo start --dev-client --port "$IOS_Q_PORT" --max-workers 2 &   # from your own copy
xcrun simctl openurl "$IOS_Q_UDID" \
  "<scheme>://expo-development-client/?url=http%3A%2F%2F127.0.0.1%3A$IOS_Q_PORT&disableOnboarding=1"
ios-q run maestro --who P5 --why "smoke es" -- maestro --udid "$IOS_Q_UDID" test -e LANG=es --include-tags smoke .maestro
ios-q run maestro --who P5 --why "smoke en" -- maestro --udid "$IOS_Q_UDID" test -e LANG=en --include-tags smoke .maestro
ios-q release "$IOS_Q_LEASE"; kill %1             # the simulator stays booted for the next phase
```

- **Fingerprint-keyed dev client.** `devclient` keys the cached simulator build on `@expo/fingerprint`'s hash, which is also the hash `expo run:ios` gives a build-cache provider. The first agent on a fingerprint builds it; every other copy installs it in seconds. `install` does nothing if the simulator already has that build. To make `expo run:ios` use the cache itself, see [references/dev-client-cache.md](references/dev-client-cache.md).
- **Metro per agent, simulator per lease.** Each agent runs its own Metro, from its own copy, on the port its lease gives it (8081 + n). The dev client opens that Metro with `simctl openurl`. `disableOnboarding=1` stops the dev menu's first-launch sheet from covering the app, and `disableFab=1` hides the floating button. Set `EXPO_NO_DEV_MENU=1` and SDK 58's CLI adds the equivalent flags to the URLs it prints.
- **Reset the app, not the simulator.** Use `xcrun simctl terminate <udid> <bundle id>`, or `launchApp: clearState: true` in the flow.

### When to rebuild native

Rebuild only when `devclient has` fails, which means the fingerprint changed. That happens when you add, remove or upgrade a package with native code; change a config plugin, `app.json` fields that reach native code (`ios.*`, plugins, scheme, permissions), the Podfile or `Podfile.properties.json`; or upgrade the Expo SDK or React Native. A JS, TS, asset or style change never needs a rebuild: Metro serves it. Rebuild only under the `build` lane.

### Release builds: only for performance and the phone

A Release build can't load JS from Metro, so every JS change means building it again. Make one only to measure performance (cold start, scrolling, memory) or to put the app on the iPhone. Then build under the `build` lane and keep it out of the simulator pool's routine.

## The simulator pool

- **One simulator per project, kept booted.** It's named for the project (`Acme`, then `Acme B`) and runs the newest runtime, plus the phone's iOS version when you are chasing a phone bug. `ios-q sim <project>` lends a booted simulator that no one else holds. If none is free, it boots the next simulator in the pool, within the boot lane and the 3-booted ceiling, and otherwise waits in line.
- **Leased, not owned.** The lease ends when you release it, when your process ends, or when its `--max` runs out. The simulator stays booted for the next agent.
- **Never `simctl shutdown`, never `simctl erase`, never kill CoreSimulatorService.** Other agents are using them. If a simulator is wedged, stop and tell the user; don't repair it by wiping it.
- **Set dark mode and language inside the flow** (`setDarkMode`, a launch argument or the app's own language switch). Don't change them on the simulator between runs.

## Tests: Jest first, then a small Maestro set, then the phone

- **Jest with fake repositories** covers everything that is logic: reducers, date maths, validation, i18n strings in every language, navigation state, and each screen's states rendered with React Native Testing Library. It takes seconds, needs no lane, and is where most of what Maestro flows assert today belongs.
- **Maestro is a tagged smoke set** on `testID`s (`tapOn: {id: …}`): launch, sign-in, the paths that make money, one screen per feature. Run it once per language over the whole folder, so the driver starts once per language, with `setDarkMode` and `clearState` inside the flows. Run no more than two at once, and stop at the first red flow: read its debug output instead of running the suite again.
- **The phone** is for push delivery, universal links, camera and photos, Face ID, haptics, and the feel of scrolling and cold start. The agent installs, pulls logs and screenshots; the person checks.

Flows, timeouts and flakiness under load: [references/testing.md](references/testing.md).

## The physical iPhone

The cable is fastest. Run everything under the `device` lane:

```sh
ios-q run device --who P5 --why "push check" -- xcrun devicectl device install app --device <udid> App.app
ios-q run device --who P5 --why "push check" -- xcrun devicectl device process launch --device <udid> --terminate-existing --console <bundle id>
```

`devicectl` can also take screenshots, record the screen and copy crash logs (Xcode 27.2). Agents can automate install, launch, logs, screenshots and uninstall. A person has to handle Developer Mode, Trust This Computer, re-pairing after an iOS update, permission alerts and Face ID. Signing and provisioning traps, such as a cached profile without a capability added later or free teams and Associated Domains: [references/device.md](references/device.md).

## Don't

- **EAS in any form.** `eas build --local` refuses to run without a login and adds nothing over prebuild + `xcodebuild`.
- **Maestro Cloud or hosted macOS CI to go faster.** It costs money every run, and a simulator `.app` built here installs in seconds.
- **More simulators to "parallelise" Maestro.** On a loaded Mac every flow gets slower and flakier.
- **A Release build for Maestro**, or a clean build because "it might help".
- **Shutting down, erasing or deleting a simulator** you didn't create for yourself in this phase.
- **Playwright, `docker build` or wide Jest outside the `heavy` lane.**

## The brief, for an orchestrator to put in mobile agents' prompts

> **iOS on this Mac is shared.** Read the `expo-ios-agents` skill before any build, install, simulator or Maestro step. Everything that builds, boots, installs or drives a simulator goes through `ios-q`; never run `xcodebuild`, `expo run:ios`, `pod install`, `simctl boot` or `maestro` bare. Use `ios-q run <lane> --who <your card> --why "<what>" -- <command>`, which waits its turn, tells you your place, and always releases. Do not boot a simulator: `eval "$(ios-q sim <project> --who <your card> --why …)"` lends you the project's booted one and a Metro port. Install the dev client for the current fingerprint with `devclient install "$IOS_Q_UDID"`, build it only if that fails (under the build lane), start Metro from your own copy on `$IOS_Q_PORT` and open it with `simctl openurl`. Release builds only for performance checks and the phone. Never shut down, erase or delete a simulator, and never kill CoreSimulatorService. Jest first; Maestro once per language on the smoke tag; stop at the first red flow and read its output. Playwright and Docker builds only in the `heavy` lane. Never use `ios-q prioritize`.

## Reference files

| File | Read it when |
|---|---|
| [references/ios-q.md](references/ios-q.md) | using or configuring the queue: every command, setting, exit code; the state files; an old lock living alongside it |
| [references/build-caches.md](references/build-caches.md) | builds of a fresh copy are slow: ccache with `base_dir`, Xcode's compilation cache with prefix mapping, and how to measure hits |
| [references/dev-client-cache.md](references/dev-client-cache.md) | sharing dev-client builds: `devclient`, and a local build-cache provider so `expo run:ios` installs instead of building |
| [references/testing.md](references/testing.md) | writing or running tests: Jest with fake repositories, Maestro habits under load, alternatives |
| [references/device.md](references/device.md) | putting a build on the iPhone: devicectl steps, logs, screenshots, signing and provisioning |
| [references/disk.md](references/disk.md) | the disk is filling up: `scripts/disk-sweep`, what it keeps, and the rest of the usual suspects |
