# Tests: Jest first, a small Maestro set, then the phone

Every Maestro flow costs a simulator, a driver, half a minute to a minute on a quiet Mac, and a lot more on a busy one. Most of what flows end up asserting (strings, state, which screen comes next) runs under Jest in seconds and never flakes. Push each check down to the cheapest layer that can prove it.

## Jest, with fake repositories

- **What goes here:** reducers and stores, date and money maths, validation, i18n strings in every language the app ships (missing keys, plurals), navigation state, and every screen's states (loading, empty, error, full) rendered with React Native Testing Library.
- **Fake repositories, not mocked fetch.** Put data access behind a small interface (`PostsRepo.list()`, `.create()`) and give tests an in-memory version with seeded data. Screens and hooks take the repository from context. The tests then read like the product ("an empty week shows the empty state"), not like HTTP.
- **Navigation:** render the navigator with mocked `react-native-reanimated` and `react-native-gesture-handler` (both ship mocks), press, and assert the destination screen's content.
- **What Jest can't see:** native code, layout, real gestures, the keyboard, dark mode rendering, animations. That's Maestro's job.
- **No lane is needed** for Jest with up to 4 workers. Use `--maxWorkers=4`; anything wider goes under `ios-q run heavy`.

## Maestro, as a tagged smoke set

- **A small set:** launch, sign-in, the paths that make money, and one screen per feature. Tag them `smoke`, and run the rest only when a change touches them.
- **Find elements by id:** `tapOn: { id: "save-button" }` on a `testID`. Use regex on text only where an id can't exist (system sheets, permission alerts). On iOS, a container with `accessible={true}` swallows its children's taps and ids, so put `accessible` on the leaf.
- **One invocation per language, over the whole folder:** `maestro --udid "$IOS_Q_UDID" test -e LANG=es --include-tags smoke .maestro`, then the same with `en`. The driver starts once per invocation, which is a large part of the cost.
- **Dark mode inside the flow** (`setDarkMode: true`, Maestro 2.9+) and **`launchApp: { clearState: true }`** at the start. Don't reconfigure the simulator between runs.
- **A dev client in the flow:** after `clearState` the app opens on the dev launcher, so open your Metro in the flow:

  ```yaml
  - launchApp: { clearState: true }
  - openLink: "<scheme>://expo-development-client/?url=http%3A%2F%2F127.0.0.1%3A${PORT}&disableOnboarding=1&disableFab=1"
  ```

  Pass the port with `-e PORT=$IOS_Q_PORT`.

## Maestro habits under load

- **Always under the lane:** `ios-q run maestro --who … --why … -- maestro --udid "$IOS_Q_UDID" test …`. Never more than two at once on the Mac, and one per simulator. `run` takes the udid from `--udid` or `--device`.
- **A hard ceiling on every run.** The maestro lane's default `--max` is 25 minutes, and `run` stops the command when it runs out. A dead driver (an HTTP 500 from the XCTest runner marks the connection dead, and nothing reconnects) then can't hold the lane.
- **Environment:**

  ```sh
  export MAESTRO_DRIVER_STARTUP_TIMEOUT=180000   # the driver starts slowly on a busy Mac
  export MAESTRO_CLI_NO_ANALYTICS=true MAESTRO_DISABLE_UPDATE_CHECK=true
  ```

- **Generous waits, few of them.** Use `extendedWaitUntil` with a long timeout where the app really does wait on something. Every lookup polls the accessibility tree, and at high load each poll takes longer.
- **Clear text with long-press → Select All → `eraseText: 1`.** Don't use `eraseText: 3000`: it's capped at 100, documented as flaky, and has killed drivers.
- **Reduce Motion** shortens settle time: `xcrun simctl spawn "$IOS_Q_UDID" defaults write com.apple.Accessibility ReduceMotionEnabled -bool true`. Check that it takes on your runtime.
- **Stop at the first red flow.** Read its debug output (`~/.maestro/tests/<run>/`: the screenshot, the hierarchy and the command log), fix the cause, then run that flow alone. Running the suite again on a busy Mac buys a different random failure.
- **Sharding across simulators** needs more booted simulators, and on one Mac it makes every flow slower. Don't.

## Other drivers, when YAML written blind isn't enough

- **`maestro mcp`:** `inspect_screen`, `take_screenshot`, and `run` with inline YAML. It lets an agent look before it writes a flow.
- **callstack's `agent-device`:** a CLI and MCP server. It returns an accessibility snapshot with refs, presses by ref, exports what it did as Maestro YAML, and claims physical-iPhone support through its own XCTest runner. Unproven here; trial it with one agent first.
- **`idb`** (`brew install facebook/fb/idb-companion`, `pip install fb-idb`): tap, type, describe-all, screenshot, record. It's the lightest of all, with no settle logic.
- **Detox:** real synchronisation (it waits for timers, network and animations) and new-architecture support, but a Jest runner and a third-party Expo config plugin to maintain. Expo documents Maestro.
- **XCUITest:** the only one of these that drives a physical iPhone officially, but its tests are Swift written against React Native's accessibility tree.

## Only on the phone

Push delivery, universal links and the Associated Domains path, camera and photos, Face ID, haptics, the feel of scrolling and cold start, and anything that needs a real network. The agent installs the build, launches it, pulls logs and screenshots; a person checks. See device.md.
