---
name: agent-sessions
description: Give AI agents a safe way to check an app's admin panel in production when sign-in is a magic link, OAuth or anything else an agent cannot finish on its own. A separate agent user; a command inside the app's container that writes an hour's session straight into the auth tables, records it in an audit table and prints the cookie on stdout only; a read-only rule enforced in one place; revocation that deletes nothing; and a helper on the developer's machine that mints over ssh + docker exec and loads the cookie into a headless browser or curl without printing it. Covers Better Auth (in detail), Supabase Auth and Auth.js / NextAuth. Use this whenever someone says agents cannot log in to the admin, wants an agent to "check the admin in prod", look at a signed-in page, verify a deploy behind a login, an "agent login", "agent session", "service account for the panel", "impersonate admin for testing", or asks how a coding agent can see what the owner sees, even if they only ask to "mint a session" or "get a cookie for the admin".
---

# Agent sessions: an hour in the admin for an agent

The owner signs in with a link sent to their inbox, so an agent working on the app cannot see the
panel in production. It checks the deploy, the data and a local dev server, then asks the owner to
look. This recipe closes that gap without weakening sign-in for anyone:

- **A separate agent user** (say "Agent", `agent@<domain>`). Its changes are logged under its own
  name, and it is never an admin by allowlist, so no magic link ever reaches it.
- **A command inside the app's container** writes a session for it straight into the auth tables,
  ending in an hour at most. It records the session in an audit table and prints the cookie on
  stdout only. No endpoint is added and nothing listens on the network. The container already holds
  the database and the auth secret, and getting into the container takes ssh access to the server.
- **The grant in the audit table is the authority.** The app lets the agent's session in only while
  its row there is live: not past its end, not revoked, and for the user it was minted for. The
  auth library's own session row is not trusted on its own, because libraries stretch sessions on
  use.
- **Read-only unless the mint says `--write`,** enforced in one function every admin check goes
  through.
- **A helper on the developer's machine** runs the command over ssh, keeps the cookie in memory,
  drives Playwright or curl with it, and revokes the session when it is done.

Read this file, then the reference for the app's auth library and the two templates, which come from
a working Next.js 16 + Better Auth + Drizzle app with Postgres on a VPS (Docker Swarm via Dokploy).

## The decisions, and why

- **A user of its own, not the owner's account.** History, logs and "edited by" then name the
  agent, and the owner's sessions are never touched. Pick an address that cannot receive mail: no
  route in the domain's mail forwarding and no catch-all. Then the address can never get a sign-in
  link or an account at an identity provider. Refuse to mint when the address is in the admin
  allowlist, which would make it a full admin with a magic link.
- **Minted in the container, not by an endpoint.** An HTTP route that hands out sessions is a new
  attack surface that must be authenticated by something, and that something becomes the real
  password. `docker exec` is guarded by ssh, which already guards everything else on the server.
  The output of `docker exec` never reaches the container's logs.
- **The command refuses to run anywhere else.** Two conditions together: a marker the image sets
  (`ENV APP_CONTAINER=web`) and `/.dockerenv`, which Docker creates in every container, Swarm tasks
  included. A laptop holding the production `.env` could otherwise mint production sessions. Outside
  a container, allow only a database on `localhost`, so the same command works in development.
- **An audit table, never deleted, with no foreign keys.** One row per mint: session id (never the
  token), user id, email, agent name, card or ticket, write flag, host, issued, ends, revoked. With
  no foreign keys it outlives the session and the user. It doubles as the grant the app checks.
- **The grant, not the session row, decides.** Better Auth refreshes a session on its first request
  once `expiresAt - expiresIn + updateAge <= now`. A one-hour session in an app with 90-day sessions
  meets that at once and becomes a 90-day session. Auth.js database sessions do the same with
  `updateAge`. So the app checks the grant on every request. Keep the session row honest as well
  where the library allows it (a hook that keeps an agent session's end), but never rely on that
  alone.
- **Read-only by default, one rule for every write.** Pages, lists and data queries are GETs with
  no body. A Next.js server action carries a `Next-Action` header; a tRPC mutation, a form post or
  an upload carries a body (`content-type`). So `refused = agent && !write && (has('next-action')
  || has('content-type'))`, checked in the function every page, action, route handler and
  procedure already calls (`getSession` / `requireAdmin`). A new action is covered without anyone
  remembering to. Do not try to list the dangerous actions: the list is always out of date.
- **`--write` is per session and needs a card.** Ask for it only when the task is to change
  something. Every change is logged under the agent's address, and the audit row says which card
  it was for.
- **Revoking deletes nothing.** Stamp `revoked_at` on the grant and end the session
  (`expires_at = now()`). Better Auth removes an expired session row the next time its cookie is
  presented; that is the library's housekeeping.
- **The helper revokes when it is done.** Each call mints its own session, uses it, and revokes it
  in a `finally` and on SIGINT/SIGTERM. The hour is only the backstop for a helper that was killed.
  Several steps go in one script rather than in many calls.
- **The cookie is never printed, pasted, saved or put in argv.** It goes from the ssh child's stdout
  into the helper's memory, then into `context.addCookies` or curl's stdin (`curl -H @-`). Argv shows
  in `ps`, and files get committed. The session id may be printed: it opens nothing.
- **The agent is not a visitor.** Leave its requests out of analytics and logs the way admins are
  left out, and refuse anything that would email its address (a "send me a test" button).

## Build it

1. **Schema.** Add the audit table next to the auth tables (`references/<library>.md` has the
   columns), generate the migration, and apply it to production before deploying the code that
   reads it.
2. **The grant check.** A small server-only module: `agentGrant(sessionId, userId)` (live row, or
   null), `isAgentUser(userId)` (has any row), `isAgentSession(sessionId)`.
3. **The admin check.** Wherever the app decides "is this an admin", accept either an allowlisted
   address or a live grant, and return the grant on the session (`agent: { write } | null`). Add
   the read-only rule there. The pattern for a Next.js app:

   ```ts
   const lookup = cache(async () => {
     const session = await auth.api.getSession({ headers: await headers() })
     if (!session) return null
     if (isAdminEmail(session.user.email)) return { ...session, agent: null }
     const grant = await agentGrant(session.session.id, session.user.id)
     return grant ? { ...session, agent: grant } : null
   })

   async function refused(session) {
     if (!session.agent || session.agent.write) return false
     const request = await headers()
     return request.has('next-action') || request.has('content-type')
   }

   export const getSession = cache(async () => {          // route handlers, tRPC
     const session = await lookup()
     return session && !(await refused(session)) ? session : null
   })

   export async function requireAdmin() {                 // pages and server actions
     const session = await lookup()
     if (!session) redirect('/login')
     if (await refused(session)) throw new Error('This agent session is read-only (mint it with --write)')
     return session
   }
   ```

4. **Library hooks** (see the reference): no sign-in may create a session for an agent user, and a
   refresh must not move an agent session's end.
5. **The command**, from `templates/agent-session.mts`: `mint --card <id> [--agent <name>]
   [--minutes 1-60] [--write]`, `revoke (--session <id> | --all)`, `list`. It is self-contained
   (Node 24 runs the TypeScript as it is) and talks to Postgres with `postgres`. In a Next.js
   standalone image the traced server keeps its own copy of `postgres` where only the server finds
   it, so copy the package next to the script and put a wrapper on the PATH:

   ```dockerfile
   ENV APP_CONTAINER=web
   COPY --from=build --chown=node:node /app/apps/web/scripts/agent-session.mts ./apps/web/scripts/
   COPY --from=build --chown=node:node /app/node_modules/.pnpm/postgres@*/node_modules/postgres ./apps/web/scripts/node_modules/postgres/
   RUN printf '#!/bin/sh\nexec node /app/apps/web/scripts/agent-session.mts "$@"\n' > /usr/local/bin/agent-session \
     && chmod 755 /usr/local/bin/agent-session
   ```

   Put this before `USER node`, since writing `/usr/local/bin` needs root. Prove these steps in a
   throwaway image before pushing: build a two-stage Dockerfile that only installs and copies, then
   run `agent-session list` in it against a local database
   (`-e DATABASE_URL=postgres://you@host.docker.internal:5432/app`). Run it once more without the
   marker to see it refuse.
6. **The helper**, from `templates/agent-admin.mts`: `open <path>... [--shot file]`,
   `run <steps.mjs>`, `curl <path> -- <curl options>`, `list`, `revoke`, plus `--local` for the dev
   server. It finds the running, healthy container with
   `docker ps -q -f name=<service> -f health=healthy | head -1`. It validates every argument
   against `^[\w.:@#-]+$` before putting it on the ssh command line. It tries the installed Chrome
   first (`chromium.launch({ channel: 'chrome' })`) so nothing needs downloading. Add
   `playwright-core` as a dev dependency of the app.
7. **Docs.** One page in the repo (`docs/agent-sessions.md`) with the commands, the rules and the
   proof, and a few lines in the project's CLAUDE.md / AGENTS.md telling agents to use the helper
   and never the database by hand.

## Prove it before calling it done

Locally against a dev server, then in production after the deploy:

- `open` a panel page: it lands on that page (not `/login`), and the shell names the agent.
- read-only: press a harmless save as a read-only agent and see it refused, with the row and its
  history unchanged; POST to an upload route and get 401. In production, use only probes that
  cannot change anything even if the rule failed (an empty upload, for instance).
- `--write` (locally only): the same save goes through and the history names the agent. Undo it.
- no stretching: after a few requests, the session row's end still equals the grant's.
- expiry: mint `--minutes 1`, ask for a panel page (200), wait past the end, ask again (redirect to
  the login or 401). In production, run it as a `run` script that waits.
- `revoke --all` ends every live one; `list` shows them as revoked.

## When the auth library is not Better Auth

The shape stays the same: agent user, audit-table grant as the authority, container command,
read-only rule, helper. Only the mint changes:

- **Supabase Auth**: mint through the admin API rather than raw SQL, because Supabase sessions are
  signed JWTs. See `references/supabase.md`.
- **Auth.js / NextAuth**: with database sessions, insert into `sessions`, and the cookie is the raw
  token. With JWT sessions, encode a JWT with the app's secret and carry the grant id in it. See
  `references/authjs.md`.
- **Anything else**: read the library's source for three things before writing code: how it names
  the session cookie (and its `__Secure-` / `__Host-` prefix on https), how it signs or encodes the
  value, and when it extends a session. Never guess these.
