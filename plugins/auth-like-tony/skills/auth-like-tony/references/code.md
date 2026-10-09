# The code

From a working project on Next.js 16, Drizzle on Postgres, next-intl and a pnpm
monorepo. `@project/db` stands for wherever the project keeps `db` and its schema;
`project` is the cookie prefix and the product name in copy. Keep the comments.

Contents:

1. `.env.example` block
2. The shared Mailpit: setup, scripts, containers, runs on production data
3. `next.config.ts` bits
4. `packages/db/src/schema/auth.ts`
5. `lib/email/send.ts`
6. The magic-link email
7. `lib/auth.ts`
8. `lib/auth-client.ts`
9. `app/api/auth/[...all]/route.ts`
10. `lib/admin.ts`
11. Login page and form
12. Admin layout and sign-out
13. Proxy matcher and headers
14. Using `requireAdmin()` in an action
15. Signing in from a phone over Tailscale (development)

---

## 1. `.env.example` block

```sh
# --- Better Auth (admin login by magic link) --------------------------------
# Generate with: openssl rand -base64 32
BETTER_AUTH_SECRET=
# On this project's own port, the one its `dev` script passes to `next dev --port`.
BETTER_AUTH_URL=http://localhost:3000

# --- Email ------------------------------------------------------------------
# Development sends to the machine's shared Mailpit, a background service every
# project uses (`pnpm dev` starts it if it is down). Inbox at http://localhost:8025,
# where `tag:project` shows only this project's mail. It needs no user or password.
# From a container, SMTP_HOST=host.docker.internal. Production is AWS SES over
# SMTP: .env.prod must set all four, or it falls back to Mailpit's values here.
# With SMTP_HOST empty, emails are printed to the server console instead.
SMTP_HOST=127.0.0.1
SMTP_PORT=1025
SMTP_USER=
SMTP_PASSWORD=
EMAIL_FROM="Project <hola@project.com>"
# The admins, separated by commas. Only these addresses can sign in to the
# panel (by a link sent by email).
ADMIN_EMAIL=
```

Production (`.env.prod`, or the host's project settings): `BETTER_AUTH_URL` is
the public origin, `SMTP_HOST=email-smtp.<region>.amazonaws.com`, `SMTP_PORT=587`,
user and password are the SES SMTP credentials (not the IAM keys), and
`EMAIL_FROM` is a verified identity.

## 2. The shared Mailpit

One Mailpit serves every project on the machine. Once per machine, not per
project:

```sh
brew install mailpit
brew services start mailpit   # now, at every login, and again if it dies
```

SMTP is then on port 1025 and the inbox on `http://localhost:8025`; projects
send to `127.0.0.1:1025`. Homebrew's service runs Mailpit with its defaults,
which listen on every interface, not only `127.0.0.1`, and keep the latest 500
messages across all projects. Mention both commands in the README next to
`pnpm dev`.

Root `package.json`:

```json
{
  "scripts": {
    "dev": "pnpm mail; turbo run dev",
    "mail": "nc -z 127.0.0.1 1025 >/dev/null 2>&1 || brew services start mailpit"
  }
}
```

Single app, no turbo: `"dev": "pnpm mail; next dev --port 3000"`, with the
project's own port (the one in `BETTER_AUTH_URL`). In a turbo monorepo the
port goes in the web app's own `dev` script.

- `pnpm mail` only ever starts the service, and only when nothing answers on
  1025. Nothing in a project stops it, so when one project's `pnpm dev` exits,
  the others keep their inbox. Two projects starting at once both run `brew
  services start`; the second is told it is already started and carries on.
- `;` rather than `&&`: on a machine without Homebrew or Mailpit the app still
  starts, and `brew`'s error at the top of the output says why mail fails.
- No `concurrently` for mail: Mailpit is not a child of `pnpm dev`, so it is
  not killed with it.

**Containers.** A service running in Docker sends to the same Mailpit, with
`SMTP_HOST=host.docker.internal` and `SMTP_PORT=1025` in its environment
(OrbStack and Docker Desktop both resolve that name to the Mac). No compose
file has a Mailpit service: one would fight the shared Mailpit for port 1025,
or split the mail into a second inbox.

**Moving a project off its own Mailpit.** Take `mailpit` out of `dev`, and
`concurrently` too if Mailpit was its only reason. Point `SMTP_HOST` and
`SMTP_PORT` at `127.0.0.1:1025` wherever the project had ports of its own
(`.env`, `.env.example`, dev scripts). Delete any Mailpit service from compose.
Add the tag (section 5), and give the app its own port if it was on Next's
default.

**Runs on production data.** Anything running on this machine is development,
whatever database it points at: `dev:prod`, a rehearsal on a copy of
production, a one-off script. All of it sends to the shared Mailpit, tagged
with the project's slug, and none of it sends through SES. No project starts a
Mailpit of its own for it, on other ports or anywhere else.

`.env.prod` holds the SES credentials, so a script that loads it sets the four
SMTP variables back to the shared Mailpit itself. Jajotopa's `dev:prod` does it
in an env file for `env-cmd`:

```json
"dev:prod": "pnpm mail; env-cmd -f scripts/dev-prod-env.mjs -- next dev --port 3000"
```

```js
const env = {
  ...prod, // .env.prod, parsed
  // The machine's shared Mailpit instead of SES, so real addresses from the production
  // database never get mail. Inbox at http://localhost:8025, filter `tag:project`.
  SMTP_HOST: '127.0.0.1',
  SMTP_PORT: '1025',
  SMTP_USER: '',
  SMTP_PASSWORD: '',
  // ...and local values for every other way out: webhooks, push, WhatsApp, ad conversions.
}

export default env
```

Without a script file, the same values go in front of `env-cmd --no-override -f
.env.prod`, which then leaves them alone (Holapy's `dev:prod`). Either way it
runs `pnpm mail` like `dev` does, and `next dev` sets `NODE_ENV=development`,
so the mail carries the tag.

## 3. `next.config.ts` bits

```ts
const nextConfig: NextConfig = {
  serverExternalPackages: ['postgres', 'nodemailer'],
  async headers() {
    return [
      {
        source: '/(admin|login)/:path*',
        headers: [{ key: 'X-Robots-Tag', value: 'noindex, nofollow' }],
      },
    ]
  },
}
```

## 4. `schema/auth.ts`

Drizzle with `casing: 'snake_case'` in both `drizzle.config.ts` and
`drizzle()`; column names are written in camelCase and stored in snake_case.
Better Auth's drizzle adapter maps its models to these exports by key
(`user`, `session`, `account`, `verification`, `rateLimit`).

```ts
import { bigint, boolean, index, integer, pgTable, text, timestamp } from 'drizzle-orm/pg-core'

/**
 * Better Auth's tables. Its adapter reads and writes these by name, so the
 * shape follows what Better Auth expects. Every user is an admin: there is
 * no public sign-up.
 */

export const user = pgTable('user', {
  id: text().primaryKey(),
  name: text().notNull(),
  email: text().notNull().unique(),
  emailVerified: boolean().notNull().default(false),
  image: text(),
  createdAt: timestamp({ withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp({ withTimezone: true })
    .notNull()
    .defaultNow()
    .$onUpdate(() => new Date()),
})

export const session = pgTable(
  'session',
  {
    id: text().primaryKey(),
    userId: text()
      .notNull()
      .references(() => user.id, { onDelete: 'cascade' }),
    token: text().notNull().unique(),
    expiresAt: timestamp({ withTimezone: true }).notNull(),
    ipAddress: text(),
    userAgent: text(),
    createdAt: timestamp({ withTimezone: true }).notNull().defaultNow(),
    updatedAt: timestamp({ withTimezone: true })
      .notNull()
      .defaultNow()
      .$onUpdate(() => new Date()),
  },
  (t) => [index('session_user_id_idx').on(t.userId)],
)

export const account = pgTable(
  'account',
  {
    id: text().primaryKey(),
    userId: text()
      .notNull()
      .references(() => user.id, { onDelete: 'cascade' }),
    accountId: text().notNull(),
    providerId: text().notNull(),
    accessToken: text(),
    refreshToken: text(),
    idToken: text(),
    accessTokenExpiresAt: timestamp({ withTimezone: true }),
    refreshTokenExpiresAt: timestamp({ withTimezone: true }),
    scope: text(),
    password: text(),
    createdAt: timestamp({ withTimezone: true }).notNull().defaultNow(),
    updatedAt: timestamp({ withTimezone: true })
      .notNull()
      .defaultNow()
      .$onUpdate(() => new Date()),
  },
  (t) => [index('account_user_id_idx').on(t.userId)],
)

export const verification = pgTable(
  'verification',
  {
    id: text().primaryKey(),
    identifier: text().notNull(),
    value: text().notNull(),
    expiresAt: timestamp({ withTimezone: true }).notNull(),
    createdAt: timestamp({ withTimezone: true }).notNull().defaultNow(),
    updatedAt: timestamp({ withTimezone: true })
      .notNull()
      .defaultNow()
      .$onUpdate(() => new Date()),
  },
  (t) => [index('verification_identifier_idx').on(t.identifier)],
)

/**
 * Counts login attempts. Kept in the database because on serverless every
 * function instance has its own memory, and a counter there would not count.
 */
export const rateLimit = pgTable('rate_limit', {
  id: text().primaryKey(),
  key: text().notNull().unique(),
  count: integer().notNull(),
  lastRequest: bigint({ mode: 'number' }).notNull(),
})
```

Export it from the schema index (`export * from './auth'`), then the project's
`db:generate` and `db:migrate`.

## 5. `lib/email/send.ts`

```ts
import nodemailer, { type Transporter } from 'nodemailer'

export type Email = {
  to: string
  subject: string
  html: string
  text: string
  replyTo?: string
  headers?: Record<string, string>
}

const globalForMail = globalThis as unknown as { __projectMail?: Transporter }

/**
 * Development mail lands in the Mailpit every project on this machine shares,
 * so it is tagged to let the inbox be filtered to this project (`tag:project`).
 * Development only: an unset NODE_ENV sends no tag either, so production mail
 * never carries it.
 */
const devHeaders = process.env.NODE_ENV === 'development' ? { 'X-Tags': 'project' } : undefined

/**
 * AWS SES over SMTP in production, the machine's shared Mailpit in development
 * (no user or password). Null when there is no SMTP_HOST.
 */
function transporter(): Transporter | null {
  const { SMTP_HOST, SMTP_USER, SMTP_PASSWORD } = process.env
  if (!SMTP_HOST) return null

  const port = Number(process.env.SMTP_PORT ?? 587)
  return (globalForMail.__projectMail ??= nodemailer.createTransport({
    host: SMTP_HOST,
    port,
    secure: port === 465,
    auth: SMTP_USER && SMTP_PASSWORD ? { user: SMTP_USER, pass: SMTP_PASSWORD } : undefined,
    pool: true,
    maxConnections: 3,
    // SES allows a fixed number of messages a second. Stay well under it.
    rateLimit: 10,
  }))
}

/** ADMIN_EMAIL, which may list several addresses separated by commas. */
export function adminEmails(): string[] {
  return (process.env.ADMIN_EMAIL ?? '')
    .split(',')
    .map((email) => email.trim().replace(/^"|"$/g, '').toLowerCase())
    .filter(Boolean)
}

/** Where notices go: every admin, as one address line. */
export function adminEmail(): string | null {
  return adminEmails().join(', ') || null
}

/** Sends, or prints to the console when there is no SMTP to send through. */
export async function sendEmail(email: Email): Promise<void> {
  const from = process.env.EMAIL_FROM ?? 'Project <hola@project.com>'
  const transport = transporter()

  if (!transport) {
    console.info(
      `\n[email, not sent: SMTP is not configured]\nTo: ${email.to}\nSubject: ${email.subject}\n\n${email.text}\n`,
    )
    return
  }

  await transport.sendMail({ from, ...email, headers: { ...email.headers, ...devHeaders } })
}
```

The transporter is kept on `globalThis` so hot reloads in development do not
open a new SMTP pool each time.

The tag's value is the project's slug, the same as the cookie prefix. It is
keyed on `NODE_ENV === 'development'`, not `!== 'production'`: `next dev` sets
it, while a process started without it (a worker, a one-off script) sends no
tag rather than risk tagging production mail. A worker run in development
gets the tag by setting `NODE_ENV=development` in its dev script.

## 6. The magic-link email

Whatever the project's email layout is (here, small helpers in
`lib/email/layout.ts` that build table-based HTML with inline styles: `layout`,
`heading`, `paragraph`, `button`, `small`), the message is:

```ts
export function magicLinkEmail(to: string, signInUrl: string, locale: Locale): Email {
  const c = copy[locale]
  return {
    to,
    subject: c.signInSubject,           // "Your link to sign in to the Project panel"
    text: `${c.signInBody}\n\n${c.signInButton}: ${signInUrl}\n\n${c.signInIgnore}`,
    html: layout({
      locale,
      preview: c.signInBody,
      homeUrl: siteUrl,
      body: heading(c.signInTitle) + paragraph(c.signInBody) + button(c.signInButton, signInUrl),
      footer: small(c.signInIgnore),
    }),
  }
}
```

Copy, es / en:

- Subject: "Tu enlace para entrar al panel de Project" / "Your link to sign in to the Project panel"
- Title: "Entrar al panel" / "Sign in to the panel"
- Body: "Tocá el botón para entrar al panel de Project. El enlace sirve una sola vez." / "Press the button to sign in to the Project panel. The link works once."
- Button: "Entrar" / "Sign in"
- Footer: "El enlace vence en 15 minutos. Si no lo pediste, ignorá este correo." / "The link expires in 15 minutes. If you did not ask for it, ignore this email."

Always give both `text` and `html`. Escape everything interpolated into HTML.
If the layout also prints the raw link under the button (for clients that block
buttons), give that paragraph `word-break:break-all;overflow-wrap:anywhere;`: a
sign-in URL has nowhere to break, and on a phone it runs out of the card.

## 7. `lib/auth.ts`

```ts
import { account, db, rateLimit, session, user, verification } from '@project/db'
import { betterAuth } from 'better-auth'
import { drizzleAdapter } from 'better-auth/adapters/drizzle'
import { nextCookies } from 'better-auth/next-js'
import { magicLink } from 'better-auth/plugins'
import { magicLinkEmail } from '@/lib/email/messages'
import { adminEmails, sendEmail } from '@/lib/email/send'
import { siteUrl } from '@/lib/env'

/** How long a sign-in link works, in minutes. */
const MAGIC_LINK_MINUTES = 15

/** The addresses in ADMIN_EMAIL are the admins. Nobody else can sign in. */
export function isAdminEmail(email: string): boolean {
  return adminEmails().includes(email.trim().toLowerCase())
}

/**
 * The admin login: a link sent by email, no passwords. An address in
 * ADMIN_EMAIL gets its account on its first sign-in. Any other address is
 * answered the same way and sent nothing.
 */
export const auth = betterAuth({
  baseURL: process.env.BETTER_AUTH_URL ?? siteUrl,
  secret: process.env.BETTER_AUTH_SECRET,
  database: drizzleAdapter(db, {
    provider: 'pg',
    schema: { user, session, account, verification, rateLimit },
  }),
  session: {
    expiresIn: 60 * 60 * 24 * 14,
    updateAge: 60 * 60 * 24,
  },
  databaseHooks: {
    user: {
      create: {
        // A second lock behind the one in sendMagicLink.
        before: async (data) => (isAdminEmail(data.email) ? { data } : false),
      },
    },
  },
  rateLimit: {
    enabled: process.env.NODE_ENV === 'production',
    storage: 'database',
    window: 60,
    max: 60,
    customRules: {
      '/sign-in/magic-link': { window: 300, max: 5 },
      '/magic-link/verify': { window: 60, max: 10 },
    },
  },
  advanced: {
    cookiePrefix: 'project',
  },
  plugins: [
    magicLink({
      expiresIn: MAGIC_LINK_MINUTES * 60,
      storeToken: 'hashed',
      sendMagicLink: async ({ email, url }) => {
        if (!isAdminEmail(email)) return
        await sendEmail(magicLinkEmail(email, url, 'es'))
      },
    }),
    // Must stay last: it lets server actions set the session cookie.
    nextCookies(),
  ],
})

export type Session = typeof auth.$Infer.Session
```

Bilingual panel: the locale comes from the panel's cookie, read
inside `sendMagicLink`, so the email matches the language of the login page:

```ts
const chosen = (await cookies()).get(ADMIN_LOCALE_COOKIE)?.value
await sendEmail(magicLinkEmail(email, url, isLocale(chosen) ? chosen : DEFAULT_LOCALE))
```

`siteUrl` is `NEXT_PUBLIC_SITE_URL`, falling back to the host's production URL
variable and then `http://localhost:3000`, never with a trailing slash.

## 8. `lib/auth-client.ts`

```ts
import { magicLinkClient } from 'better-auth/client/plugins'
import { createAuthClient } from 'better-auth/react'

export const authClient = createAuthClient({ plugins: [magicLinkClient()] })
```

## 9. `app/api/auth/[...all]/route.ts`

```ts
import { toNextJsHandler } from 'better-auth/next-js'
import { auth } from '@/lib/auth'

export const { GET, POST } = toNextJsHandler(auth)
```

## 10. `lib/admin.ts`

```ts
import { headers } from 'next/headers'
import { redirect } from 'next/navigation'
import { cache } from 'react'
import { type Session, auth, isAdminEmail } from './auth'

/**
 * The session, only while its address is still in ADMIN_EMAIL: taking an
 * address out of the list signs that person out on their next request.
 */
export const getSession = cache(async (): Promise<Session | null> => {
  const session = await auth.api.getSession({ headers: await headers() })
  return session && isAdminEmail(session.user.email) ? session : null
})

/**
 * For pages: sends anyone without a session to the login. Every admin page
 * and every admin action calls this itself. The layout's check is not
 * enough, because an action can be called without rendering any layout.
 */
export async function requireAdmin(): Promise<Session> {
  const session = await getSession()
  if (!session) redirect('/login')
  return session
}
```

`cache()` makes one `getSession()` per request however many pages, layouts
and components call it.

## 11. Login page and form

`app/(admin)/login/page.tsx`:

```tsx
import { redirect } from 'next/navigation'
import { LoginForm } from '@/components/admin/auth-forms'
import { getSession } from '@/lib/admin'

// A sign-in link that failed comes back here with ?error=.
type Props = { searchParams: Promise<{ error?: string }> }

export default async function LoginPage({ searchParams }: Props) {
  if (await getSession()) redirect('/admin')
  const { error } = await searchParams
  return <LoginForm linkFailed={Boolean(error)} />   // inside the project's auth page frame
}
```

`components/admin/auth-forms.tsx` (react-hook-form + zod, as the rest of the
project's forms; swap `t(...)` for plain strings in a single-language app):

```tsx
'use client'

import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { authClient } from '@/lib/auth-client'

const loginSchema = z.object({
  email: z.string().trim().toLowerCase().min(1, 'required').pipe(z.email('email')),
})

/** Asks for an address and sends it a sign-in link. */
export function LoginForm({ linkFailed = false }: { linkFailed?: boolean }) {
  const [sentTo, setSentTo] = useState<string | null>(null)
  const [problem, setProblem] = useState<string | null>(
    linkFailed ? 'The link expired or was already used. Ask for a new one.' : null,
  )
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<z.infer<typeof loginSchema>>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: '' },
  })

  if (sentTo) {
    return (
      <div role="status">
        <p>
          If <strong>{sentTo}</strong> is a panel account, we sent it a sign-in link. It expires in 15 minutes.
        </p>
        <button type="button" onClick={() => setSentTo(null)}>Use another email</button>
      </div>
    )
  }

  return (
    <form
      noValidate
      onSubmit={handleSubmit(async (values) => {
        setProblem(null)
        // Same answer whether the address is an admin or not.
        const { error } = await authClient.signIn.magicLink({
          email: values.email,
          callbackURL: '/admin',
          errorCallbackURL: '/login',
        })
        if (error) {
          setProblem(
            error.status === 429
              ? 'Too many attempts. Wait a few minutes and try again.'
              : 'We could not send the link. Try again.',
          )
          return
        }
        setSentTo(values.email)
      })}
    >
      <label>
        Email
        <input type="email" autoComplete="email" autoFocus {...register('email')} />
      </label>
      {errors.email && <p role="alert">{errors.email.message}</p>}
      {problem && <p role="alert">{problem}</p>}
      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? 'Sending' : 'Send me a link'}
      </button>
    </form>
  )
}
```

Spanish copy, voseo: "Entrar", "Correo", "Enviarme un enlace", "Enviando",
"Si <strong>{email}</strong> es una cuenta del panel, le enviamos un enlace
para entrar. Vence en 15 minutos.", "Usar otro correo", "El enlace venció o ya
fue usado. Pedí uno nuevo.", "Demasiados intentos. Esperá unos minutos y probá
de nuevo.", "No pudimos enviar el enlace. Probá de nuevo."

## 12. Admin layout and sign-out

`app/(admin)/admin/layout.tsx`:

```tsx
import type { ReactNode } from 'react'
import { AdminShell } from '@/components/admin/shell'
import { requireAdmin } from '@/lib/admin'

export const dynamic = 'force-dynamic'

export default async function AdminLayout({ children }: { children: ReactNode }) {
  const session = await requireAdmin()
  return <AdminShell userName={session.user.name || session.user.email}>{children}</AdminShell>
}
```

Sign-out, in a client component in the shell:

```tsx
<button
  type="button"
  onClick={async () => {
    await authClient.signOut()
    router.push('/login')
    router.refresh()
  }}
>
  Sign out
</button>
```

## 13. Proxy matcher and headers

If the site has locale routing (next-intl), keep the panel out of it.
`proxy.ts` (Next 16; `middleware.ts` before):

```ts
export const config = {
  // The public site only. The admin panel, the API and files have no locale.
  matcher: '/((?!api|admin|login|_next|_vercel|.*\\..*).*)',
}
```

The `noindex` header is in section 3.

## 14. Using `requireAdmin()` in an action

Every exported server action in the admin's actions file starts the same way,
before validating input:

```ts
'use server'

export async function deleteItem(itemId: string): Promise<void> {
  await requireAdmin()
  if (!id.safeParse(itemId).success) return
  await db.delete(items).where(eq(items.id, itemId))
  redirect('/admin/items')
}
```

A quick audit: `grep -L requireAdmin` over the admin pages and `grep -c
requireAdmin` against `grep -c "^export async function"` in the actions file
should match.

## 15. Signing in from a phone over Tailscale (development)

The sign-in link points at `localhost`, which a phone cannot open. With one
switch in `.env`, the dev server is reached at the computer's Tailscale address
instead. Changing the link alone is not enough, for three reasons:

- Better Auth builds the link **and the redirect after it** from `baseURL`
  (`new URL(callbackURL, baseURL)` in the magic-link plugin), so with only the
  email rewritten the phone signs in and is then sent to `localhost`.
- Better Auth checks the `Origin` of requests that carry a cookie against
  `baseURL` and `trustedOrigins`. With `baseURL` on the Tailscale address,
  signing out on the computer at `localhost` fails unless `localhost` is
  trusted too.
- Next 16 blocks the dev server's scripts and HMR for any host but `localhost`,
  so without `allowedDevOrigins` the page loads on the phone but never hydrates:
  the form does nothing.

`.env.example`:

```sh
# Development only: open the dev server from your phone over Tailscale. When on,
# sign-in links and Better Auth use http://TAILSCALE_IP:<BETTER_AUTH_URL's port>
# instead of localhost; localhost keeps working on the computer. `tailscale ip -4`
# prints the address.
TAILSCALE_ENABLED=false
TAILSCALE_IP=
```

`lib/auth.ts`, replacing the `baseURL` line of section 7:

```ts
/** The origin as written in .env: the computer's own, usually localhost. */
const localUrl = process.env.BETTER_AUTH_URL ?? siteUrl

/**
 * Development on a phone over Tailscale: with TAILSCALE_ENABLED on, the
 * sign-in link and Better Auth's redirect after it use TAILSCALE_IP (same
 * port) instead of localhost, which the phone cannot reach.
 */
function tailscaleUrl(): string | null {
  if (process.env.TAILSCALE_ENABLED !== 'true') return null
  const ip = process.env.TAILSCALE_IP
  if (!ip) throw new Error('TAILSCALE_ENABLED is on but TAILSCALE_IP is empty. Check .env')
  const url = new URL(localUrl)
  url.hostname = ip
  return url.origin
}

const tailscale = tailscaleUrl()

export const auth = betterAuth({
  baseURL: tailscale ?? localUrl,
  // localhost stays trusted, so signing out on the computer still passes the origin check.
  trustedOrigins: tailscale ? [localUrl] : undefined,
  // ...the rest of section 7
})
```

`next.config.ts`:

```ts
const nextConfig: NextConfig = {
  // Next blocks the dev server's scripts for hosts other than localhost; this lets
  // a phone on the tailnet load them (see TAILSCALE_ENABLED). Dev only.
  allowedDevOrigins: process.env.TAILSCALE_IP ? [process.env.TAILSCALE_IP] : [],
}
```

Notes:

- If the project validates its env in one module (zod), do the swap there
  instead, with `TAILSCALE_ENABLED: z.stringbool().default(false)`, and
  overwrite the app's URL variable itself. Then every link the app emails
  follows, not only sign-in, and keep the original in a second field for
  `trustedOrigins`. That is how Jajotopa does it (`env/server.ts`).
- Other links built from the site's URL (an email layout's home link) keep
  pointing at `localhost` with the version above. Harmless for signing in;
  swap them too if the phone should follow them.
- `next dev` loads `.env.local` and fills in any variable not already set. So a
  `dev:prod` script that loads `.env.prod` through `env-cmd` still picks up
  `TAILSCALE_*` from `.env.local`, and the switch works there too (on whatever
  port that script uses). Its email still goes to the shared Mailpit, never SES
  (section 2), so a link with the Tailscale address reaches nobody.
- The phone only follows the link if it can open the email, in the shared
  inbox (search `tag:project`). `tailscale serve --bg --http=8025
  http://127.0.0.1:8025` should publish the inbox on the tailnet at
  `http://<tailscale ip>:8025` (not tried yet; `tailscale serve reset` undoes
  it).
