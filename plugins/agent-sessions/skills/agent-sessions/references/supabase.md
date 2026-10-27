# Supabase Auth

Checked against @supabase/ssr 0.7 and @supabase/auth-js 2.x. Supabase sessions are a signed JWT
access token plus a refresh token, issued by the Auth server (GoTrue). Do not insert rows into
`auth.sessions` by hand or sign JWTs yourself (projects on asymmetric signing keys cannot). Mint
through the admin API, from the container that holds the service-role key.

## Minting without sending an email

```ts
const admin = createClient(SUPABASE_URL, SERVICE_ROLE_KEY, { auth: { persistSession: false } })
// The agent user, once: email_confirm so it never needs a mailbox.
await admin.auth.admin.createUser({ email: AGENT_EMAIL, email_confirm: true, user_metadata: { name: 'Agent' } })
// A sign-in link, returned to us instead of emailed.
const { data: link } = await admin.auth.admin.generateLink({ type: 'magiclink', email: AGENT_EMAIL })
// Spend it at once, here, for a session.
const anon = createClient(SUPABASE_URL, ANON_KEY, { auth: { persistSession: false } })
const { data } = await anon.auth.verifyOtp({ token_hash: link.properties.hashed_token, type: 'email' })
// data.session: access_token (a JWT with a session_id claim), refresh_token, expires_at
```

`generateLink` sends nothing. The link is spent inside the container and never leaves it.

## Make it an hour

- The access token lives for the project's JWT expiry (an hour by default). **Do not hand the
  refresh token to the helper:** put an empty one in the cookie. When the access token ends, the
  app's middleware fails to refresh it and the agent is signed out. Then revoke the real refresh
  token at once with `admin.auth.admin.signOut(access_token, 'local')`, which ends that session's
  refresh tokens. The access token keeps working until it expires, so write the grant's end as the
  token's `expires_at`.
- The grant table keys on the JWT's `session_id` claim (`sessionId` in the table). The app's admin
  check reads the claims (`getClaims()` or `getUser()`), then the grant by `session_id` and `sub`.
- Revoke: stamp the grant, and `admin.auth.admin.signOut(<a token of that session>, 'local')`, or
  delete the session's row from `auth.sessions` (the Auth server's own table; this is the one place
  where removing a row is the revocation itself). Since the app checks the grant on every request,
  stamping alone closes the panel even while the JWT has minutes left.

## The cookie (@supabase/ssr)

- **Name**: the client's `storageKey`, by default `sb-<project ref>-auth-token`, where the ref is
  the first label of the Supabase URL's hostname.
- **Value**: `base64-` followed by base64url(JSON.stringify(session)). Encoding `base64url` is the
  default in 0.6+; `cookieEncoding: 'raw'` stores the JSON as it is. The session JSON has
  `access_token`, `refresh_token`, `expires_in`, `expires_at`, `token_type`, `user`.
- **Chunking**: a value longer than 3180 characters is split into `<name>.0`, `<name>.1`, … Set
  every chunk; the `user` object usually pushes it over.
- The cookie is not httpOnly by design (the browser client reads it). Set `secure` on https and
  `sameSite: 'Lax'`.

Easiest: let the library build the cookies. In the container, create a server client whose
`cookies.setAll` collects into an array, call `auth.setSession({ access_token, refresh_token: '' })`,
and print the collected `{ name, value }` pairs as the JSON line the helper reads.

## Read-only and hooks

The read-only rule and the grant check live in the app (the same `refused` function). Supabase has
no hook to refuse a sign-in for one user. The agent cannot sign in anyway (its address has no
mailbox, and no password is ever set), and the grant check refuses any session that has no grant.
Row Level Security sees the agent as an ordinary authenticated user. If the panel relies on an
`is_admin` claim or a role, give the agent the same claim and let the app's read-only rule do the
narrowing. Or, stricter: a separate `agent` role whose RLS policies allow only `select`.
