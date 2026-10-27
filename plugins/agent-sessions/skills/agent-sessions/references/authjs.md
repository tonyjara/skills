# Auth.js (NextAuth v5) and NextAuth v4

Check against the installed version: `@auth/core/lib/utils/cookie.js` (names) and
`@auth/core/jwt.js` (encoding). Names below are as of @auth/core 0.3x / next-auth 5 and 4.24.

## Which strategy?

`session: { strategy }` is `database` when an adapter is configured, `jwt` otherwise.

## Database sessions

- **Rows**: `users` (or `user`), then `sessions` (`sessionToken`, `userId`, `expires`), named as the
  adapter names them. The token is any long random string. Auth.js stores it as it is and looks the
  session up by it.
- **Cookie**: v5 `authjs.session-token`, v4 `next-auth.session-token`, with `__Secure-` on https.
  The value is the raw `sessionToken`: no signing, no encoding.
- **Stretching**: on use, when `expires - maxAge + updateAge < now`, the adapter's `updateSession`
  moves `expires` to `now + maxAge` (30 days by default). Wrap the adapter so an agent session keeps
  its end:

  ```ts
  const base = DrizzleAdapter(db)
  const adapter = {
    ...base,
    async updateSession(session) {
      if (session.expires && (await isAgentSession(session.sessionToken))) {
        const { expires: _kept, ...rest } = session
        return base.updateSession!(rest)
      }
      return base.updateSession!(session)
    },
  }
  ```

  Key the grant by the session token's hash, or by a session id column if the schema has one.
  Never store the token itself in the audit table.
- **Refuse sign-ins for the agent**: the `signIn` callback returns `false` when
  `user.email === AGENT_EMAIL`.

## JWT sessions

There is no row to insert, so the grant table is the only thing that can revoke.

- Mint in the container with the library's own encoder and the app's secret, carrying the grant id:

  ```ts
  import { encode } from '@auth/core/jwt'          // v4: import { encode } from 'next-auth/jwt'
  const name = secure ? '__Secure-authjs.session-token' : 'authjs.session-token'
  const value = await encode({
    token: { sub: agentUserId, email: AGENT_EMAIL, name: 'Agent', agentGrant: grantId },
    secret: process.env.AUTH_SECRET!,
    salt: name,                                    // v5 needs the cookie name as salt; v4 has no salt
    maxAge: 60 * 60,
  })
  ```

- The `jwt` callback runs on every request and re-issues the cookie with a fresh `exp` (it slides).
  The grant decides anyway: in the admin check, read `token.agentGrant` and refuse unless its row
  is live. Optionally, in the `jwt` callback, return `null` for a token whose grant is no longer
  live (v5), which signs the agent out.
- Large tokens are chunked (`.0`, `.1`) above about 4 KB; an agent token is small.

## Read-only

The same `refused` function in the app's `requireAdmin` / `auth()` wrapper: an agent session with
`write` off is refused any request that carries `Next-Action` or a body.
