# When the app runs where nothing can be run: Vercel, with the database on a VPS

Worked out on Subignite (Next.js 16 on Vercel, Better Auth 1.7, Drizzle, Postgres 18 on a VPS
behind PgBouncer), 2026-10-27. Read it when the app has no container you can `docker exec`
into: Vercel, Netlify, any serverless host.

## The problem

The skill's mint needs two things in one place: the database and the session signing secret.
On Vercel there is no shell, and a secret stored as "sensitive" cannot be read back (`vercel env
pull` gives placeholders). Do not rotate the secret to learn it. Rotation signs every user out,
and it may break whatever else the secret encrypts: Better Auth's JWT plugin keeps its private
keys encrypted with it.

## The split

- **The database mints.** Write the mint as a SQL function in the app's database (a custom
  migration), and run it from a shell inside the Postgres container:
  `ssh <vps> 'docker exec -i <pg container> psql -U <app role> -d <db> -X -q -A -t -v ON_ERROR_STOP=1'`,
  with the SQL on stdin. The official Postgres image trusts the local socket for every role, so
  no password is involved. The function writes the session row and the grant. It returns a
  random **one-time key** and stores only the key's SHA-256. It needs no secret.
- **The app signs, once.** A Better Auth plugin endpoint, `POST /api/auth/agent-session/claim`
  with `{ key }`, claims the grant atomically. The grant must be unclaimed, not revoked, not past
  its end, and issued under five minutes ago. The endpoint then calls Better Auth's own
  `setSessionCookie(ctx, session, true)`, so the prefix, the domain (`crossSubDomainCookies`) and
  the cookie cache are exactly the library's. `true` is `dontRememberMe`: a browser-session cookie
  plus `dont_remember`, which turns Better Auth's refresh off for that browser. Every other key
  gets the same 401.

This adds an endpoint, which the skill avoids, but the endpoint mints nothing. It only exchanges a
DB-minted, single-use, five-minute key for the cookie of a session that already exists. Guessing a
key is as hard as guessing a session token.

**Alternatives that were rejected:**

- **Better Auth's `bearer` plugin.** It signs any raw token itself, so every token in a database
  dump would become a live session. A browser also cannot scope an `Authorization` header to one
  host.
- **The `one-time-token` plugin.** Its `generate` endpoint lets any script on the page turn an
  httpOnly session into a portable token, unless you set `disableClientRequest`. Its `verify`
  returns the raw token in the body, and you would be writing rows in its private
  `verification` format.

## The guard on the mint

```sql
v_client inet := inet_client_addr();   -- NULL on the unix socket
IF v_client IS NOT NULL AND NOT (v_client <<= inet '127.0.0.0/8' OR v_client = inet '::1') THEN
  RAISE EXCEPTION 'agent_session_mint runs only from inside the database''s container (docker exec psql), not over the network';
END IF;
```

The app (through PgBouncer) and a laptop on the direct port both arrive over the container network
with an address, so neither can mint. Check this on the server first:
`select coalesce(host(client_addr),'socket'), application_name from pg_stat_activity where datname = current_database()`.
On Subignite, PgBouncer arrived from 10.0.1.8 and the Mac (through Traefik) from 10.0.1.10.
Loopback stays allowed, so tests and a local database work. Revoke has no guard: an emergency
revoke must work from anywhere that can write.

## The SQL (Subignite's, renamed)

Randomness without pgcrypto: `gen_random_uuid()` draws from the server's strong random source.
Two of them with the dashes taken out make 64 hex characters, 244 random bits. `sha256()` is
built into Postgres 11 and later.

```sql
CREATE OR REPLACE FUNCTION public.agent_session_mint(p_card text, p_agent text, p_minutes integer, p_write boolean, p_host text)
RETURNS text AS $$
DECLARE
  v_email constant text := 'agent@example.com';
  v_label constant text := '^[A-Za-z0-9_.:@#-]{1,64}$';
  v_client inet := inet_client_addr();
  v_user uuid;
  v_session text := gen_random_uuid()::text;
  v_token text := replace(gen_random_uuid()::text, '-', '') || replace(gen_random_uuid()::text, '-', '');
  v_key text := replace(gen_random_uuid()::text, '-', '') || replace(gen_random_uuid()::text, '-', '');
  v_expires timestamptz;
BEGIN
  -- the guard above; then p_card, p_agent and p_host against v_label, and p_minutes 1..60
  v_expires := now() + make_interval(mins => p_minutes);
  INSERT INTO "user" (id, name, email, email_verified) VALUES (gen_random_uuid(), 'Agent', v_email, false)
  ON CONFLICT (email) DO NOTHING;
  SELECT id INTO v_user FROM "user" WHERE email = v_email;
  -- refuse while the agent holds the app's top role (platform_admins, an ADMIN_EMAIL entry, …)
  INSERT INTO session (id, user_id, token, expires_at, user_agent)
  VALUES (v_session, v_user, v_token, v_expires, 'agent-session: ' || p_agent || ' ' || p_card);
  INSERT INTO agent_sessions (session_id, user_id, email, agent, card, write, host, key_hash, expires_at)
  VALUES (v_session, v_user, v_email, p_agent, p_card, p_write, p_host, encode(sha256(convert_to(v_key, 'UTF8')), 'hex'), v_expires);
  RETURN json_build_object('key', v_key, 'session', v_session, 'expiresAt', v_expires, 'write', p_write)::text;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.agent_session_revoke(p_session_id text DEFAULT NULL) RETURNS SETOF text AS $$
  WITH revoked AS (
    UPDATE agent_sessions a SET revoked_at = now()
    WHERE a.revoked_at IS NULL AND a.expires_at > now() AND (p_session_id IS NULL OR a.session_id = p_session_id)
    RETURNING a.session_id
  ), ended AS (UPDATE session s SET expires_at = now() WHERE s.id IN (SELECT session_id FROM revoked))
  SELECT session_id FROM revoked;
$$ LANGUAGE sql;
```

Use the id format the app's Better Auth uses. With `advanced.database.generateId: () =>
crypto.randomUUID()`, session ids are UUID strings. A `handle_new_user`-style trigger gives the
inserted user its profile row.

The audit table is the skill's, plus two columns: `key_hash text not null unique` and
`claimed_at timestamptz`.

## The claim (a Better Auth plugin)

```ts
export function agentSessionPlugin() {
  return {
    id: 'agent-session',
    endpoints: {
      claimAgentSession: createAuthEndpoint(
        '/agent-session/claim',
        { method: 'POST', body: z.object({ key: z.string().regex(/^[0-9a-f]{64}$/) }) },
        async (ctx) => {
          // update agent_sessions set claimed_at = now() where key_hash = sha256(key)
          //   and claimed_at is null and revoked_at is null and expires_at > now()
          //   and issued_at > now() - interval '5 minutes' returning session_id, user_id, write
          // then the session's token by (id, user_id), then internalAdapter.findSession(token)
          if (!claimed || !found || !isAgentEmail(found.user.email)) {
            throw new APIError('UNAUTHORIZED', { message: 'Not a live agent session key' })
          }
          await setSessionCookie(ctx, found, true)
          return ctx.json({ session: found.session.id, write: claimed.write, expiresAt: claimed.expiresAt })
        },
      ),
    },
    rateLimit: [{ pathMatcher: (path) => path === '/agent-session/claim', window: 60, max: 10 }],
  } satisfies BetterAuthPlugin
}
```

Imports: `createAuthEndpoint` and `APIError` from `better-auth/api`, `setSessionCookie` from
`better-auth/cookies`. Put the plugin before `nextCookies()`.

## The helper's two differences

- **`database(statement)`:** one SQL statement, sent on the stdin of
  `ssh <vps> 'c=$(docker ps -q -f name=<pg service> | head -1); … docker exec -i "$c" psql …'`.
  Every value in it has been checked against the label regex, so it is safe inside a quoted
  literal. The Postgres container may have no healthcheck; `-f health=healthy` then matches
  nothing. With `--local`, the same statement goes through the `postgres` package to
  `DATABASE_URL_DIRECT`.
- **`claim(minted)`:** `fetch(base + '/api/auth/agent-session/claim', { method: 'POST',
  headers: { 'content-type': 'application/json', origin: base }, body })`. Then parse
  `getSetCookie()` into `{ name, value, domain }`: Playwright gets `domain` + `path: '/'` when
  the cookie has a Domain, else `url`, and curl gets `name=value; …` on stdin. Keep every cookie:
  the session token, `session_data` and `dont_remember`.

Subignite's files: `db/sql/agent-sessions.sql`, `lib/auth/agent-sessions.ts`, `lib/auth/session.ts`
(`readSession`), `scripts/agent-admin.ts`, `docs/security/agent-sessions.md`.
