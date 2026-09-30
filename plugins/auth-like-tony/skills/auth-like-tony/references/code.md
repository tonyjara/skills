# The code

From a working project on Next.js 16, Drizzle on Postgres, next-intl and a pnpm
monorepo. `@project/db` stands for wherever the project keeps `db` and its schema;
`project` is the cookie prefix and the product name in copy. Keep the comments.

Contents:

1. `.env.example` block
2. Root `package.json` scripts (Mailpit)
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

---

## 1. `.env.example` block

```sh
# --- Better Auth (admin login by magic link) --------------------------------
# Generate with: openssl rand -base64 32
BETTER_AUTH_SECRET=
BETTER_AUTH_URL=http://localhost:3000

# --- Email ------------------------------------------------------------------
# Development sends to Mailpit (started by `pnpm dev`, inbox at http://localhost:8025),
# which needs no user or password. Production is AWS SES over SMTP: .env.prod
# must set all four, or it falls back to Mailpit's values here.
# With SMTP_HOST empty, emails are printed to the server console instead.
SMTP_HOST=localhost
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

## 2. Root `package.json` scripts

```json
{
  "scripts": {
    "dev": "concurrently -n web,mail -c blue,magenta \"turbo run dev\" \"pnpm mail\"",
    "mail": "mailpit --smtp 127.0.0.1:1025 --listen 127.0.0.1:8025"
  },
  "devDependencies": { "concurrently": "^10" }
}
```

Single app, no turbo: `"dev": "concurrently -n web,mail -c blue,magenta \"next dev\" \"pnpm mail\""`.
Mailpit itself: `brew install mailpit`. Mention it in the README next to `pnpm dev`.

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
 * AWS SES over SMTP in production, Mailpit in development (no user or
 * password). Null when there is no SMTP_HOST.
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

  await transport.sendMail({ from, ...email })
}
```

The transporter is kept on `globalThis` so hot reloads in development do not
open a new SMTP pool each time.

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
