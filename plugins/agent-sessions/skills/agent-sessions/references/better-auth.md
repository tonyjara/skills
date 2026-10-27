# Better Auth

Checked against better-auth 1.7 (better-call 1.4). Re-read the installed source when the major
version differs: `dist/api/routes/session.mjs` (getSession), `dist/cookies/index.mjs` (names),
better-call's `dist/crypto.mjs` (signing).

## The audit table (Drizzle)

```ts
export const agentSessions = pgTable(
  'agent_sessions',
  {
    id: uuid().primaryKey().defaultRandom(),
    /** The `session` row's id (never its token, which is the credential). */
    sessionId: text().notNull().unique(),
    userId: text().notNull(),
    email: text().notNull(),
    agent: text().notNull(),
    card: text().notNull(),
    /** Off, the session can look at everything and change nothing. */
    write: boolean().notNull().default(false),
    /** The container that minted it. */
    host: text(),
    issuedAt: timestamp({ withTimezone: true }).notNull().defaultNow(),
    expiresAt: timestamp({ withTimezone: true }).notNull(),
    revokedAt: timestamp({ withTimezone: true }),
  },
  (t) => [index('agent_sessions_user_id_idx').on(t.userId)],
)
```

No foreign keys on purpose. With `casing: 'snake_case'` the columns are `session_id`, `user_id`,
and so on.

## Minting

- **Rows.** `user` (id, name, email, email_verified), created on the first mint with
  `on conflict (email) do nothing`. Then `session` (id, user_id, token, expires_at, user_agent),
  with `user_agent` set to something like `agent-session: <agent> <card>`, which shows in the
  session list. Then the `agent_sessions` row. All three go in one transaction.
- **Ids and token**: 32 characters of `[a-zA-Z0-9]` (Better Auth's `generateId(32)`), from
  `crypto.randomBytes` with rejection sampling (bytes under 248, modulo 62). Better Auth stores
  the token as it is and finds a session by it.
- **Cookie name**: `${prefix}.session_token`, where the prefix is `advanced.cookiePrefix` or
  `better-auth`. On https (`baseURL` starting with `https://`, or `advanced.useSecureCookies`) it
  gains `__Secure-`, so production is `__Secure-<prefix>.session_token`.
- **Cookie value**: `encodeURIComponent(`${token}.${sig}`)`, where
  `sig = base64(HMAC-SHA256(BETTER_AUTH_SECRET, token))` in standard base64 with padding. In Node:
  `createHmac('sha256', secret).update(token).digest('base64')`. Set it in a browser exactly as
  printed (already URL-encoded), with `httpOnly`, `secure` on https, `sameSite: 'Lax'`, path `/`.
- **Bearer plugin**: with `bearer({ requireSignature: true })` the same signed value works as
  `Authorization: Bearer <value>`. The cookie is simpler for a browser.
- **Cookie cache** (`session.cookieCache.enabled`): a minted session has no `session_data` cookie,
  so the first request reads the database. After that the browser may hold a cached copy for
  `maxAge`, which delays a revocation for Better Auth's own reads. The app's grant check reads the
  database every time, so the panel still closes at once.

## Hooks in `betterAuth({ databaseHooks })`

```ts
session: {
  create: {
    // An agent's sessions are minted by the command alone: no sign-in makes one.
    before: async (data) => ((await isAgentUser(data.userId)) ? false : { data }),
  },
  update: {
    // A refresh would stretch the hour to `session.expiresIn` on the first request.
    before: async (data, context) => {
      const current = context?.context.session?.session
      if (data.expiresAt && current && (await isAgentSession(current.id))) {
        return { data: { ...data, expiresAt: current.expiresAt } }
      }
      return { data }
    },
  },
},
```

Why `update.before` returns data rather than `false`: `false` makes `updateSession` return null,
and `getSession` then deletes the cookie and throws `UNAUTHORIZED` on the agent's request.
`context.context.session` is the session being refreshed: `getSession` sets it just before it
calls `updateSession`.

A sign-in can never reach the agent anyway: the magic link sends only to allowlisted addresses, and
the address has no mailbox to verify at Google or Apple. The `create` hook just makes that explicit.

## Things that bite

- `auth.api.getSession` refreshes on the server too; nothing about a server call skips it unless
  you pass `query: { disableRefresh: true }`. Do not disable refresh for everyone just for agents:
  the hook and the grant check are enough.
- `deleteUser` (if enabled) lets any session delete its own user, the agent included. The audit
  table survives that (no foreign keys), and the next mint creates the user again.
- If the admin check also compares the address with an allowlist on the client (a "you are signed
  in as" header), the agent's name shows there. That is a feature: screenshots say who looked.
