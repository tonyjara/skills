# Hosts: keeping a server patched

One host per run. The hosts are in `inventory.yaml` under `hosts:`. A host's own ops folder
(for `nytojara-vps`: `~/Desktop/Nyto/hostinger_nytojara/CLAUDE.md`) wins over this file: read
it first, and record every change where it says (its `docs/runbook.md`).

Only from the Mac with Tailscale on. Check: `ssh -o BatchMode=yes -o ConnectTimeout=10 <host> true`.
If it fails, ask the user to turn Tailscale on; never work around it.

## 1. Inventory, read-only

Run it, paste the numbers into the report, and compare with the host's entry in the inventory.

```bash
ssh <host> '
  lsb_release -ds; uname -r; uptime; ls /boot/vmlinuz-*; cat /var/run/reboot-required.pkgs 2>/dev/null
  apt list --upgradable 2>/dev/null; apt-mark showhold
  systemctl is-active unattended-upgrades; tail -20 /var/log/unattended-upgrades/unattended-upgrades.log
  docker version --format "{{.Server.Version}} {{range .Server.Components}}{{.Name}}={{.Version}} {{end}}"
  docker service ls --format "{{.Name}} {{.Image}} {{.Replicas}}"; docker ps --format "{{.Names}} {{.Image}} {{.Status}}"
  ssh -V; openssl version; tailscale version | head -1; fail2ban-client version
  sshd -T | grep -E "^(port|passwordauthentication|permitrootlogin|kbdinteractiveauthentication) "
  ss -tlnp | awk "{print \$4}" | sort -u
  systemctl --failed --no-legend'
```

Per database container: `docker exec <c> postgres --version`. Per app container:
`docker exec <c> node -v` and its Debian release. Dokploy: the image tag of service `dokploy`;
Traefik: `docker exec dokploy-traefik traefik version`.

Compare with the brief: which installed versions are below a fixed version.

## 2. What you may do without asking

- Read anything above; read logs.
- Let unattended-upgrades work (Ubuntu security origins only). Check it ran in the last day.
- `apt-get install --only-upgrade <pkg>` for Ubuntu packages that restart nothing we run
  (libraries, tmux, glib, ubuntu-pro-client), under `systemd-run` so a dropped ssh cannot cut
  dpkg. Never `cloud-init` (held on purpose on the Hostinger image) and never `snapd` ahead
  of Ubuntu's phasing.
- Rebuild nothing, restart nothing.

## 3. What you must ask first

Write the plan (what, expected downtime, rollback) and wait for the user's OK:

- **Reboots** (new kernel, `reboot-required`). Pick a quiet window: no backups (06:00–07:10 UTC
  on `nytojara-vps`), no scheduled jobs in the next 30 minutes.
- **Docker, containerd, runc** (`docker-ce*`, `containerd.io`): restarts dockerd and every
  container, Postgres included, about 20 s.
- **Tailscale** upgrade (can drop the ssh session you are on: run it under `systemd-run`).
- **Dokploy** upgrades, Traefik changes, the Postgres image or minor version, PgBouncer.
- **sshd, fail2ban, firewall, ports.**
- Redeploying any app.

**Platypost must always stay up.** It runs on `nytojara-vps` (`platypost-server-*`, host-mode
port, update order stop-first, so any restart is downtime). Before any of the above, check
nothing is about to post (Platypost's queue), say how long it will be down, and right after,
check `platypost-server` is healthy and holds its scheduler lock again.

## 4. Infrastructure tools

The tools that guard the host get updated every Sunday too, not left to drift. Put each one's
installed version next to the latest one in the brief (the brief's "Infrastructure versions"
table), and in the report write current → target and whether it was done. Each needs the
user's OK (section 3) unless it says otherwise.

**Before anything that can cut access** (Tailscale, sshd, Docker, a reboot), set up a second
way in and test it:

1. The fallback that is always there: the **hPanel browser terminal** (Hostinger hPanel → VPS →
   Browser terminal). Ask the user to open it and run `tailscale status` there before you start.
2. A public SSH path, only if the user wants it for this change: they add an hPanel firewall
   rule for port 22 **from the Mac's public IP only** (`curl -s https://ifconfig.me`), you test
   `ssh -o HostName=<public ip> <host> true` (same key; `nytojara-vps` already pins the public
   IP as its `HostKeyAlias`), and the rule is
   removed as soon as the change is checked. Never open 22 to everyone (the host's rules).
3. Run the change under `systemd-run` so it finishes even if your session drops, and set a
   deadline: if `ssh <host> true` does not work again within 3 minutes, switch to the fallback.

| Tool | How to update safely | Check after |
|---|---|---|
| **Tailscale** | `systemd-run --unit=ss-tailscale apt-get install -y --only-upgrade tailscale`. tailscaled restarts and the tailnet path drops for a few seconds; the unit finishes anyway. Reconnect with `ssh -o ConnectTimeout=10 <host> true` in a loop for up to 3 min | `tailscale version`, `tailscale status`, the Postgres direct port and the panel answer over the tailnet |
| **OpenSSH** | Comes with Ubuntu security updates (unattended-upgrades). A manual upgrade restarts `ssh.service`; open sessions stay up. Keep one session open, test a **new** login before closing it | `ssh -V`, `sshd -T` still shows key-only, `systemctl is-active ssh` |
| **Docker / containerd / runc** | `systemd-run --unit=ss-docker apt-get install -y --only-upgrade docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin docker-ce-rootless-extras`. dockerd restarts, every container with it (about 20 s); Swarm brings services back | `docker version`, every service at its count, every health URL, Platypost healthy |
| **Dokploy** | Back up first (its web-server backup to B2 has to be newer than an hour). Upgrade with the panel's update button (Web Server settings) or its installer's update; read the release notes for breaking changes. Re-check `dokploy.yml` still has the `tailnet-only` middleware: an update can rewrite it | panel loads over the tailnet and is 403 from outside, the image tag of service `dokploy`, schedules and backups still listed |
| **Traefik** | Its version is Dokploy's choice: upgrade it through Dokploy (or with a Dokploy upgrade), never `docker pull` by hand. Back up `/etc/dokploy/traefik/` first. After, the boot guard and the hand-written dynamic files must still apply | `traefik version`, every public site 200, `db.tonyjara.com:6543` answers, panel still tailnet-only |
| **fail2ban** | Ubuntu package, unattended | `fail2ban-client status sshd` |
| **PgBouncer, Postgres** | Image tag in Dokploy, same major only (section 5) | a query through each endpoint |

## 5. Doing an approved change

1. Back up any file first: `cp -p f f.bak-$(date +%Y%m%d-%H%M)`.
2. Packages: `systemd-run --unit=ss-apt --wait apt-get -y upgrade <pkgs>` (or `full-upgrade`
   for a kernel), log to a file under `/root/security-sunday-<date>/`.
3. Postgres minor: change the tag only within the same major and only to the image the host's
   rules allow (`pgvector/pgvector:pg18-trixie` on `nytojara-vps`; pull it to get the new
   minor), deploy through Dokploy, check `postgres --version` and a query through each endpoint.
4. After: every Swarm service at its count, no failed units, every `health` URL in the
   inventory answers 200, the host's monitor is quiet.
5. Record it in the host's runbook, update the host's entry in the inventory.

## Adding a host

Add it under `hosts:` in `inventory.yaml`: name, ssh alias, how to reach it, ops folder, what
runs there, who must stay up, its own ask-first rules. Run step 1 once and record the baseline.
