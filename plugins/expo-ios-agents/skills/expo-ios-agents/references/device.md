# The physical iPhone

Run everything that touches the phone under the `device` lane: `ios-q run device --who … --why … -- <command>`. The phone must be unlocked for install and launch.

## Install and run

```sh
xcrun devicectl list devices                          # name, identifier, state (connected / available over the network)
UDID=<identifier from the list>

# a Release build, signed for this phone, built under the build lane
ios-q run build --who P5 --why "release for phone" -- \
  npx expo run:ios --device "$UDID" --configuration Release --no-bundler --output .phone-build

# install again later without rebuilding
ios-q run device --who P5 --why "install" -- npx expo run:ios --device "$UDID" --binary .phone-build/App.app
# or raw:
ios-q run device --who P5 --why "install" -- xcrun devicectl device install app --device "$UDID" .phone-build/App.app
ios-q run device --who P5 --why "launch + logs" -- \
  xcrun devicectl device process launch --device "$UDID" --terminate-existing --console <bundle id>
```

- **The cable is fastest.** iOS 17+ pairs over the network and `devicectl` works over Wi-Fi after that, but a 100 MB dev client takes seconds over USB and much longer over Wi-Fi. `ios-deploy` doesn't work with iOS 17 and later.
- **A development build on the phone** loads JS from Metro on the Mac's LAN address, like the simulator, so JS changes don't need a reinstall. Phone and Mac must be on the same network, and the port must be open.
- **A Release build without reinstalling for every JS change:** a self-hosted `expo-updates` server (`updates.url`, a fingerprint `runtimeVersion`, bundles from `expo export`). It needs no Expo account, but it's worth it only once you iterate on TestFlight builds.

## Logs, screenshots, crashes

```sh
xcrun devicectl device process launch --device "$UDID" --console <bundle id>        # the app's stdout and stderr
xcrun devicectl device capture screenshot --device "$UDID" --destination shot.png      # Xcode 27.2+
xcrun devicectl device capture screen-record --device "$UDID" --destination run.mov --duration 30
xcrun devicectl device info files --device "$UDID" --domain-type systemCrashLogs       # then: device copy from …
```

For the full system log, use `log collect --device-udid "$UDID"` or `pymobiledevice3 syslog live`. Check `xcrun devicectl device --help` for what your Xcode has; the capture commands are new.

## Signing and provisioning traps

- **Where profiles live.** Xcode 16+ keeps downloaded profiles in `~/Library/Developer/Xcode/UserData/Provisioning Profiles` and still reads the old `~/Library/MobileDevice/Provisioning Profiles`.
- **A capability added later isn't in the cached profile.** Xcode asks for a new profile only when no local one satisfies the build. Add Associated Domains (or push, or App Groups) after the first build, and the old profile still signs the app, without that entitlement. The fix:
  1. confirm the App ID has the capability in the developer portal;
  2. delete the stale `.mobileprovision` for that bundle id from both folders;
  3. build with `-allowProvisioningUpdates -allowProvisioningDeviceRegistration` (`expo run:ios --device` passes both when it signs);
  4. check that the built app and its profile agree:

     ```sh
     codesign -d --entitlements - --xml App.app
     security cms -D -i App.app/embedded.mobileprovision    # Entitlements, ProvisionedDevices, ExpirationDate
     ```

- **Free personal teams** can't have Associated Domains (or push) at all, and their profiles expire after seven days. Universal links need the paid team.
- **`?mode=developer` associated domains** (`applinks:example.com?mode=developer`) need a development-signed build, plus Settings → Developer → Associated Domains Development turned on on the phone.
- **The team id** goes in the app config (`ios.appleTeamId`) or comes from the keychain's signing identity. Keep it out of shared repos if they are public.

## What agents can do, and what stays with a person

Agents can install, launch, stream logs, take screenshots and recordings, pull crash logs and uninstall, all under the `device` lane.

A person has to handle Developer Mode, Trust This Computer, re-pairing after an iOS update, permission alerts, Face ID, the Associated Domains Development toggle, and anything else that needs the phone unlocked in someone's hand. Maestro can't drive a physical iPhone. XCUITest can, and `agent-device` claims it can (unproven).
