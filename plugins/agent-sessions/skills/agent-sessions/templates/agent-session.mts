/**
 * TEMPLATE (Better Auth + Postgres): rename the marked constants, then delete this line.
 *
 * Sessions for agents that check the panel in production (docs/agent-sessions.md). It writes a
 * session for the agent user straight into Better Auth's tables, records it in `agent_sessions`,
 * and prints the signed cookie on stdout, for the helper that asked for it over ssh
 * (`scripts/agent-admin.mts`) to load into a browser. Nothing listens anywhere: it runs in the web
 * container, which holds the database and BETTER_AUTH_SECRET.
 *
 *   docker exec <web container> agent-session mint --card ABC-12 [--agent claude] [--minutes 60] [--write]
 *   docker exec <web container> agent-session revoke (--session <id> | --all)
 *   docker exec <web container> agent-session list [--limit 20]
 *
 * Locally: `pnpm agent-session …` against the local database only.
 *
 * Self-contained on purpose: the image has Node and `postgres` next to this file, not the workspace
 * (Node runs the TypeScript as it is). The tables are `packages/db/src/schema/auth.ts`.
 */
import { createHmac, randomBytes } from 'node:crypto'
import { existsSync } from 'node:fs'
import { hostname } from 'node:os'
import { parseArgs } from 'node:util'
import postgres from 'postgres'

/** The agent user (rename). Pick an address with no mailbox: no route, no catch-all. */
const AGENT_EMAIL = 'agent@example.com'
const AGENT_NAME = 'Agent'
/** About an hour, and never more: a session that outlives its task is a key left in the door. */
const MAX_MINUTES = 60
/** `advanced.cookiePrefix` in the app's Better Auth config, or 'better-auth' (rename). */
const COOKIE_PREFIX = 'better-auth'
/** A card id or an agent's name: what goes in the record, and in the helper's ssh command line. */
const LABEL = /^[\w.:@#-]{1,64}$/

function fail(message: string): never {
  process.stderr.write(`agent-session: ${message}\n`)
  process.exit(1)
}

/**
 * Production only from inside the web container (the image sets APP_CONTAINER); anywhere else,
 * only a database on this machine. `.env.prod` on a laptop is refused.
 */
function databaseUrl(): string {
  const url = process.env.DATABASE_URL
  if (!url) fail('DATABASE_URL is not set')
  const inContainer = existsSync('/.dockerenv') && process.env.APP_CONTAINER === 'web'
  const local = ['localhost', '127.0.0.1', '[::1]'].includes(new URL(url).hostname)
  if (!inContainer && !local) fail('runs only inside the web container, or against a local database')
  return url
}

/** Better Auth's ids and tokens: 32 letters and digits (`generateId(32)`). */
function randomId(length = 32): string {
  const alphabet = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
  let id = ''
  while (id.length < length) {
    for (const byte of randomBytes(length)) {
      // 248 is 62 × 4: bytes above it would favour the first letters.
      if (byte < 248 && id.length < length) id += alphabet[byte % 62]
    }
  }
  return id
}

/** The session cookie as Better Auth signs it (better-call's `signCookieValue`). */
function sessionCookie(token: string, secret: string, baseUrl: string) {
  const signature = createHmac('sha256', secret).update(token).digest('base64')
  const secure = baseUrl.startsWith('https://')
  return {
    name: `${secure ? '__Secure-' : ''}${COOKIE_PREFIX}.session_token`,
    value: encodeURIComponent(`${token}.${signature}`),
  }
}

const when = (date: Date) => date.toISOString().replace('T', ' ').slice(0, 16) + ' UTC'

async function mint(sql: postgres.Sql, args: string[]) {
  const { values } = parseArgs({
    args,
    options: {
      card: { type: 'string' },
      agent: { type: 'string', default: 'agent' },
      minutes: { type: 'string', default: String(MAX_MINUTES) },
      write: { type: 'boolean', default: false },
    },
  })
  const { card, agent, write } = values
  if (!card || !LABEL.test(card)) fail('--card is required: the card the agent works on (ABC-12)')
  if (!LABEL.test(agent)) fail('--agent: letters, digits and . _ : @ # - only')
  const minutes = Number(values.minutes)
  if (!Number.isInteger(minutes) || minutes < 1 || minutes > MAX_MINUTES) fail(`--minutes: 1 to ${MAX_MINUTES}`)

  const secret = process.env.BETTER_AUTH_SECRET
  if (!secret) fail('BETTER_AUTH_SECRET is not set')
  const baseUrl = process.env.BETTER_AUTH_URL ?? process.env.NEXT_PUBLIC_SITE_URL ?? ''
  // An admin's address would be a whole admin, magic link included.
  const admins = (process.env.ADMIN_EMAIL ?? '').split(',').map((email) => email.trim().toLowerCase())
  if (admins.includes(AGENT_EMAIL)) fail(`${AGENT_EMAIL} is in ADMIN_EMAIL; take it out first`)

  const token = randomId()
  const sessionId = randomId()
  const expiresAt = new Date(Date.now() + minutes * 60_000)
  const host = hostname()

  await sql.begin(async (tx) => {
    await tx`
      insert into "user" (id, name, email, email_verified)
      values (${randomId()}, ${AGENT_NAME}, ${AGENT_EMAIL}, false)
      on conflict (email) do nothing`
    const [agentUser] = await tx<{ id: string }[]>`select id from "user" where email = ${AGENT_EMAIL}`
    if (!agentUser) throw new Error('the agent user is missing')
    await tx`
      insert into session (id, user_id, token, expires_at, user_agent)
      values (${sessionId}, ${agentUser.id}, ${token}, ${expiresAt}, ${`agent-session: ${agent} ${card}`})`
    await tx`
      insert into agent_sessions (session_id, user_id, email, agent, card, write, host, expires_at)
      values (${sessionId}, ${agentUser.id}, ${AGENT_EMAIL}, ${agent}, ${card}, ${write}, ${host}, ${expiresAt})`
  })

  // stdout is for the helper alone: one line it reads and keeps in memory. Never paste it anywhere.
  process.stdout.write(
    `${JSON.stringify({ ...sessionCookie(token, secret, baseUrl), url: baseUrl, session: sessionId, expiresAt, write })}\n`,
  )
  process.stderr.write(
    `Session ${sessionId} for ${agent} (${card}), ${write ? 'READ-WRITE' : 'read-only'}, ` +
      `until ${when(expiresAt)}. Revoke: agent-session revoke --session ${sessionId}\n`,
  )
}

/** Ends sessions without deleting anything: the grant is stamped revoked and the session expires now. */
async function revoke(sql: postgres.Sql, args: string[]) {
  const { values } = parseArgs({ args, options: { session: { type: 'string' }, all: { type: 'boolean', default: false } } })
  if (!values.session && !values.all) fail('revoke needs --session <id> or --all')
  const revoked = await sql.begin(async (tx) => {
    const rows = await tx<{ sessionId: string }[]>`
      update agent_sessions set revoked_at = now()
      where revoked_at is null and expires_at > now()
        and ${values.all ? tx`true` : tx`session_id = ${values.session ?? ''}`}
      returning session_id as "sessionId"`
    const ids = rows.map((row) => row.sessionId)
    if (ids.length > 0) await tx`update session set expires_at = now() where id in ${tx(ids)}`
    return ids
  })
  process.stdout.write(`${revoked.length} agent session(s) revoked${revoked.length ? `: ${revoked.join(', ')}` : ''}\n`)
}

async function list(sql: postgres.Sql, args: string[]) {
  const { values } = parseArgs({ args, options: { limit: { type: 'string', default: '20' } } })
  const rows = await sql<
    { sessionId: string; agent: string; card: string; write: boolean; issuedAt: Date; expiresAt: Date; revokedAt: Date | null }[]
  >`
    select session_id as "sessionId", agent, card, write, issued_at as "issuedAt", expires_at as "expiresAt", revoked_at as "revokedAt"
    from agent_sessions order by issued_at desc limit ${Math.min(Number(values.limit) || 20, 500)}`
  const now = Date.now()
  for (const row of rows) {
    const state = row.revokedAt ? 'revoked' : row.expiresAt.getTime() <= now ? 'expired' : 'LIVE'
    process.stdout.write(
      [when(row.issuedAt), state, row.write ? 'write' : 'read', row.agent, row.card, row.sessionId].join('\t') + '\n',
    )
  }
}

const COMMANDS = { mint, revoke, list }
const [command, ...rest] = process.argv.slice(2)
if (!command || !(command in COMMANDS)) fail('usage: agent-session mint|revoke|list (see docs/agent-sessions.md)')
const sql = postgres(databaseUrl(), { prepare: false, max: 1, connect_timeout: 10, onnotice: () => {} })
try {
  await COMMANDS[command as keyof typeof COMMANDS](sql, rest)
} catch (error) {
  fail(error instanceof Error ? error.message : String(error))
} finally {
  await sql.end({ timeout: 5 })
}
