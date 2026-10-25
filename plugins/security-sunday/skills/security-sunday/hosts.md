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
nothing is about to post (Platypost's queue: the `list_queue` MCP tool), say how long it will be
down, and right after, check `platypost-server` is healthy and holds its scheduler lock again:
`/api/health` answers only on loopback, so `docker exec <its container> node -e
'fetch("http://127.0.0.1:7727/api/health").then(r=>r.text()).then(console.log)'` (`connected`);
the lock is the granted `advisory` row of `pg_locks` joined to `pg_stat_activity` in
`platypost-db` (`psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"` in its container, SQL on stdin),
application `platypost-leader (MV)`.

Also before a Docker or Traefik restart: tell the agent sessions that deploy to the host
(`ListAgents`, the busy ones) to hold their deploys, and avoid :20 (Pasapy's hourly `catch-up`)
and the backup window.

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
| **Tailscale** | `systemd-run --unit=ss-tailscale apt-get install -y --only-upgrade tailscale`. tailscaled restarts and the tailnet path drops for a few seconds; the unit finishes anyway. Reconnect with `ssh -o ConnectTimeout=10 <host> true` in a loop for up to 3 min (2026-10-25: back at +8 s) | `tailscale version`, `tailscale status` (the Mac `direct`, not relayed), `tailscale debug prefs` unchanged, `iptables -t nat -S ts-postrouting` has no MASQUERADE, the Postgres direct port, the panel and Platypost's 7727 answer over the tailnet |
| **OpenSSH** | Comes with Ubuntu security updates (unattended-upgrades). A manual upgrade restarts `ssh.service`; open sessions stay up. Keep one session open, test a **new** login before closing it | `ssh -V`, `sshd -T` still shows key-only, `systemctl is-active ssh` |
| **Docker / containerd / runc** | `apt-get -s` first (only upgrades, nothing new). Then `systemd-run --unit=ss-docker --setenv=DEBIAN_FRONTEND=noninteractive apt-get install -y --only-upgrade -o Dpkg::Options::=--force-confold docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin docker-ce-rootless-extras`, logged to a file. dockerd restarts, every container with it; Swarm brings services back (2026-10-25: about 33 s from outside, all at count after 60 s). The monitor then posts one "task failed" per service: the tasks the stop ended, harmless | `docker version`, every service at its count and the same containers per service as before, `daemon.json` unchanged, every health URL, Platypost healthy and holding its lock |
| **Dokploy** | Back up first (its web-server backup to B2 has to be newer than an hour). Upgrade with the panel's update button (Web Server settings) or its installer's update; read the release notes for breaking changes. Re-check `dokploy.yml` still has the `tailnet-only` middleware: an update can rewrite it | panel loads over the tailnet and is 403 from outside, the image tag of service `dokploy`, schedules and backups still listed |
| **Traefik** | Through Dokploy, never `docker pull` by hand. Dokploy uses `traefik:v${TRAEFIK_VERSION}`, defaulting to the version in its `traefik-setup` (a Dokploy upgrade does not recreate Traefik). For a newer one: back up `/etc/dokploy/traefik/`; dry-run the new image on a copy of it with `--network none` (no ACME, not the real `acme.json`) and diff its `/api/{http,tcp}/{routers,middlewares,services}` with the live container's (`api.insecure` is on, port 8080 inside, not published); `docker service update --env-add TRAEFIK_VERSION=<v> dokploy` (panel back in ~40 s); then API `settings.writeTraefikEnv` with what `settings.readTraefikEnv` returns (the panel's Traefik → Environment → Save): Dokploy pulls, removes and recreates the container with the same env and extra ports, about 10 s without HTTPS or :6543. The recreate drops any `docker update` memory limit. Remove the env pin once Dokploy's default is newer | `traefik version`, the API diff unchanged, every public site 200 with its certificate, `db.tonyjara.com:6543` answers, panel and :5432 still tailnet-only |
| **fail2ban** | Ubuntu package, unattended | `fail2ban-client status sshd` |
| **PgBouncer** | Test the new image first: a throwaway container (never named `pgbouncer`) on `dokploy-network` with the live File Mounts read-only, and a login to every pooled database through it (passwords on stdin from the Mac, `psql` in the pg18 container). Then only the `image:` line of the compose in Dokploy (`compose.update`) and `compose.deploy`: start-first, no failed login on 2026-10-25 | a pooled login per database through the public address, `pg_stat_activity` on pg18 shows every app role coming from the new task |
| **Postgres** | Image tag in Dokploy, same major only (section 5) | a query through each endpoint |
| **holapy-nav** (nginx, Valhalla, VROOM, pmtiles) | In the holapy repo, `ops/holapy-nav/docker-compose.yml`, applied with its `dokploy-sync.sh --deploy` (replaces only changed services), commit and push there. nginx: `nginx -t` with the new image on the live template first | `bin/smoke-test.sh` on the host (18 checks) |

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
