# One dev client per fingerprint, shared by every copy

A development build only changes when native code changes, and `@expo/fingerprint` hashes exactly that: native dependencies, config plugins, the native parts of the app config, the Podfile and its properties. Key the simulator `.app` on that hash and the first agent on a fingerprint builds it, while every other copy installs it in seconds. Nothing here needs an Expo account.

The cache is a folder of tarballs, `~/Library/Caches/ios-q/builds/` (or `IOS_Q_BUILD_CACHE`):

```
<project>-<fingerprint>-<Debug|Release>.tar.gz    the .app
<project>-<fingerprint>-<Debug|Release>.meta      bundle id, a hash of the code, when, from where
<project>-<fingerprint>-<Debug|Release>/App.app   extracted once, on first use
```

`<project>` is the `name` in the app's `package.json` without its npm scope. The fingerprint is `@expo/fingerprint`'s default hash, the one `expo run:ios` computes for a build-cache provider, so the script and the provider below share entries. The configuration is part of the key because the hash doesn't include it.

Only simulator builds go in. A device build is signed for particular phones, and `expo run:ios` itself uses the cache only for simulators.

## `scripts/devclient`

```sh
devclient key                     # acme-3f9c…-Debug
devclient has                     # exit 0 when cached
devclient install "$IOS_Q_UDID"   # install unless the simulator already has this build; prints the bundle id
devclient save .dev-client/App.app
devclient path                    # the extracted .app, for: npx expo run:ios --binary "$(devclient path)"
devclient list ; devclient prune --keep 3
```

`install` compares the code hash (the executable plus the `.debug.dylib`, which holds the app's code in debug builds) against what the simulator has installed, so it never reinstalls for nothing. Run it inside your `sim` lease. Run the build that fills the cache under the `build` lane:

```sh
devclient install "$IOS_Q_UDID" || {
  ios-q run build --who P5 --why "dev client $(devclient key)" -- \
    npx expo run:ios --device "$IOS_Q_UDID" --no-bundler --output .dev-client
  devclient save .dev-client/*.app && devclient install "$IOS_Q_UDID"
}
```

Computing the fingerprint takes a few seconds, since it reads the project. Compute it once per phase, not once per flow.

## A local build-cache provider for `expo run:ios`

SDK 53 and later read `buildCacheProvider` from the app config. Before building for a simulator, `expo run:ios` calls the provider's `resolveBuildCache`. A path to a `.app` it gets back becomes `--binary`, so the CLI installs that build and never runs `xcodebuild`. After a simulator build, the CLI calls `uploadBuildCache` with the built `.app`. (`--no-build-cache` skips the lookup.) The provider below uses the same folder and key as `devclient`:

```js
// build-cache-provider.js, next to app.json
// app.json: { "expo": { "buildCacheProvider": { "plugin": "./build-cache-provider.js" } } }
const fs = require('fs');
const os = require('os');
const path = require('path');
const crypto = require('crypto');
const { execFileSync } = require('child_process');

const CACHE = process.env.IOS_Q_BUILD_CACHE || path.join(os.homedir(), 'Library/Caches/ios-q/builds');

function key({ projectRoot, fingerprintHash, runOptions }) {
  let name = path.basename(projectRoot);
  try { name = require(path.join(projectRoot, 'package.json')).name || name; } catch {}
  name = name.replace(/^@[^/]+\//, '').replace(/[^A-Za-z0-9._-]/g, '_');
  return `${name}-${fingerprintHash}-${runOptions?.configuration || 'Debug'}`;
}

function plist(app, field) {
  return execFileSync('plutil', ['-extract', field, 'raw', path.join(app, 'Info.plist')]).toString().trim();
}

function codeHash(app) {
  const exe = plist(app, 'CFBundleExecutable');
  const h = crypto.createHash('sha256');
  for (const f of [exe, `${exe}.debug.dylib`]) {
    const p = path.join(app, f);
    if (fs.existsSync(p)) h.update(fs.readFileSync(p));
  }
  return h.digest('hex').slice(0, 16);
}

module.exports = {
  async resolveBuildCache(args) {
    if (args.platform !== 'ios') return null;
    const k = key(args);
    const tgz = path.join(CACHE, `${k}.tar.gz`);
    if (!fs.existsSync(tgz)) return null;
    const dir = path.join(CACHE, k);
    if (!fs.existsSync(dir)) {
      const tmp = path.join(CACHE, `.extract.${process.pid}`);
      fs.rmSync(tmp, { recursive: true, force: true });
      fs.mkdirSync(tmp, { recursive: true });
      execFileSync('tar', ['-xzf', tgz, '-C', tmp]);
      try { fs.renameSync(tmp, dir); } catch { fs.rmSync(tmp, { recursive: true, force: true }); }
    }
    const app = fs.readdirSync(dir).find((f) => f.endsWith('.app'));
    return app ? path.join(dir, app) : null;
  },

  async uploadBuildCache(args) {
    const app = args.buildPath;
    if (args.platform !== 'ios' || !app.endsWith('.app')) return null;
    if (plist(app, 'CFBundleSupportedPlatforms.0') !== 'iPhoneSimulator') return null;
    const k = key(args);
    fs.mkdirSync(CACHE, { recursive: true });
    const tmp = path.join(CACHE, `.save.${process.pid}.tar.gz`);
    execFileSync('tar', ['-czf', tmp, '-C', path.dirname(app), path.basename(app)]);
    fs.writeFileSync(path.join(CACHE, `${k}.meta`),
      `bundle_id=${plist(app, 'CFBundleIdentifier')}\nsha=${codeHash(app)}\nsaved=${Math.floor(Date.now() / 1000)}\nfrom=${args.projectRoot}\n`);
    fs.renameSync(tmp, path.join(CACHE, `${k}.tar.gz`));
    fs.rmSync(path.join(CACHE, k), { recursive: true, force: true });
    return path.join(CACHE, `${k}.tar.gz`);
  },
};
```

With the provider in place, `ios-q run build -- npx expo run:ios --device "$IOS_Q_UDID"` is an install whenever someone has already built that fingerprint. It still takes the `build` lane, because a miss means a full build. To keep the provider on just this Mac, set it from `app.config.js` only when the file exists, or behind an environment variable.

`resolveBuildCache` runs before every simulator `run:ios`, and computing the fingerprint costs a few seconds. That's small next to a build, but noticeable when nothing native changed and you only wanted Metro: in that case, skip `run:ios` and use `devclient install` plus `simctl openurl`.
