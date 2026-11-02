# Disk

A full disk shows up as build failures that look like something else (`build.db: disk I/O error`, a simulator that won't boot). Keep a floor of free space, about 80 GB on a Mac that builds iOS all day, and sweep weekly.

## `scripts/disk-sweep`

```sh
disk-sweep                          # dry run: lists what would go, with sizes
disk-sweep --apply                  # removes it; refuses while ios-q's build or boot lane is held
disk-sweep --floor 100 --keep-runtime 26.6 --skip pnpm
```

| What | Removed | Kept |
|---|---|---|
| Unavailable simulators | `xcrun simctl delete unavailable` | — |
| Simulator runtimes | `xcrun simctl runtime delete <id>` | the newest per platform, `--keep-runtime`, versions a paired device runs, any with a booted simulator |
| iOS DeviceSupport | folders for iOS versions no paired device runs | all of it when no device is paired (nothing to compare against) |
| DerivedData | folders whose `info.plist` `WorkspacePath` no longer exists, untouched for an hour | everything still in use |
| pnpm store | `pnpm store prune` | packages some project references |
| dev-client cache | `devclient prune --keep 3` | the newest three per project |

It exits 1 when free space is still under the floor, and names the next suspects. Run it from a weekly job, or by hand on a quiet Mac. It never shuts down, erases or deletes a booted simulator. To delete the per-phase simulators that the pool replaced, list them with `xcrun simctl list devices`, and delete by hand those nobody uses (`xcrun simctl delete <udid>`).

## The usual suspects beyond iOS

| What | Look | Keep in check |
|---|---|---|
| Docker images, build cache, volumes | `docker system df` | `docker system prune` after a look at `docker ps -a`; add `-a --volumes` only when you know nothing needs them. Run one engine, not two. |
| Android SDK, Gradle | `du -sh ~/Library/Android ~/.gradle` | `gradle --stop`, then clear `~/.gradle/caches` while no Android work is going on; keep one system image |
| npm, bun caches | `du -sh ~/.npm ~/.bun/install/cache` | `npm cache clean --force` monthly |
| Agents' scratch copies | the folders your agents work in | remove copies older than a week whose work is merged |
| Metro caches | `$TMPDIR/metro-*` | remove when stale |

## Spotlight

Exclude build output from Spotlight in System Settings → Spotlight → Privacy (or `sudo mdutil -i off <volume>` for a dedicated volume). Exclude `~/Library/Developer`, the pnpm store (`pnpm store path`), every project's `node_modules`, the agents' scratch folders and Docker's data folder. Otherwise `mds_stores` re-indexes each build's output and takes a core while it does.
