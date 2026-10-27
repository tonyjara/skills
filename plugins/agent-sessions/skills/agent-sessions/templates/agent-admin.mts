/**
 * TEMPLATE: rename HOST, the service name in CONTAINER, PRODUCTION and LOCAL, then delete this line.
 *
 * How an agent checks the admin panel in production (docs/agent-sessions.md). It asks the web
 * container for a session over ssh (`agent-session mint`, apps/web/scripts/agent-session.mts),
 * keeps the cookie in this process's memory only, uses it, and revokes the session when it is
 * done, even after a failure or Ctrl+C. The cookie is never printed, written to a file or put on a
 * command line; the session's id, which opens nothing, is.
 *
 *   pnpm agent:admin open <path>... --card ABC-12 [--shot page.png]
 *   pnpm agent:admin run <script.mjs> --card ABC-12
 *   pnpm agent:admin curl <path> --card ABC-12 [-- <curl options>]
 *   pnpm agent:admin list | revoke
 *
 * Options: --agent <name> (who you are; $AGENT_NAME, else "claude"), --write (a session that may
 * change things; read-only otherwise), --minutes <1-60> (how long it can live; 60), --local (the
 * local site and database instead of production), --chars <n> (text printed per page; 3000).
 *
 * A `run` script exports one function, called with a page already signed in:
 *
 *   export default async ({ page, base }) => {
 *     await page.goto(`${base}/admin/sources`)
 *     await page.getByRole('button', { name: /events/i }).first().click()
 *     await page.screenshot({ path: '/tmp/sources.png' })
 *   }
 */
import { spawn } from 'node:child_process'
import { resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import { parseArgs } from 'node:util'
import { type Browser, type BrowserContext, type Page, chromium } from 'playwright-core'

/** The server, as `~/.ssh/config` names it (rename). */
const HOST = process.env.APP_VPS ?? 'my-vps'
/** The web app's running, healthy container (a Swarm task of the Dokploy service). */
const CONTAINER = 'c=$(docker ps -q -f name=app-web -f health=healthy | head -1); [ -n "$c" ] || { echo "no healthy app-web container" >&2; exit 1; }; docker exec "$c" agent-session'
const PRODUCTION = 'https://example.com'
const LOCAL = 'http://localhost:3000'
/** What `agent-session` accepts as a card or a name: safe on the ssh command line as it is. */
const LABEL = /^[\w.:@#-]{1,64}$/

type Minted = { name: string; value: string; url: string; session: string; expiresAt: string; write: boolean }

function fail(message: string): never {
  process.stderr.write(`agent-admin: ${message}\n`)
  process.exit(1)
}

const { values, positionals } = parseArgs({
  allowPositionals: true,
  options: {
    card: { type: 'string' },
    agent: { type: 'string', default: process.env.AGENT_NAME ?? 'claude' },
    write: { type: 'boolean', default: false },
    minutes: { type: 'string', default: '60' },
    local: { type: 'boolean', default: false },
    shot: { type: 'string' },
    chars: { type: 'string', default: '3000' },
  },
})
const [command, ...targets] = positionals

/** Runs `agent-session` where the session lives: in the web container, or here against the local database. */
function agentSession(args: string[]): Promise<string> {
  for (const arg of args) if (!/^[\w.:@#-]+$/.test(arg)) fail(`refusing an argument with odd characters: ${arg}`)
  const [file, argv] = values.local
    ? ['node', ['--env-file=.env', 'apps/web/scripts/agent-session.mts', ...args]]
    : ['ssh', ['-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15', HOST, `${CONTAINER} ${args.join(' ')}`]]
  return new Promise((done, failed) => {
    // stdout is caught here (it carries the cookie); stderr says what happened, for the agent to read.
    const child = spawn(file, argv, { cwd: resolve(import.meta.dirname, '../../..'), stdio: ['ignore', 'pipe', 'inherit'] })
    let out = ''
    child.stdout.on('data', (chunk: Buffer) => (out += chunk.toString()))
    child.on('error', failed)
    child.on('close', (code) => (code === 0 ? done(out) : failed(new Error(`agent-session ${args[0]} failed (${code})`))))
  })
}

async function mint(): Promise<Minted> {
  if (!values.card || !LABEL.test(values.card)) fail('--card is required: the card you are working on (ABC-12)')
  if (!LABEL.test(values.agent)) fail('--agent: letters, digits and . _ : @ # - only')
  const args = ['mint', '--card', values.card, '--agent', values.agent, '--minutes', values.minutes]
  if (values.write) args.push('--write')
  return JSON.parse(await agentSession(args)) as Minted
}

/** Holds a session for the length of `task`, and revokes it whatever happens. */
async function withSession(task: (minted: Minted, base: string) => Promise<void>) {
  const minted = await mint()
  const base = values.local ? (process.env.AGENT_BASE_URL ?? LOCAL) : PRODUCTION
  let revoked = false
  const revoke = async () => {
    if (revoked) return
    revoked = true
    process.stderr.write((await agentSession(['revoke', '--session', minted.session])).toString())
  }
  for (const signal of ['SIGINT', 'SIGTERM'] as const) {
    process.once(signal, () => void revoke().finally(() => process.exit(130)))
  }
  try {
    await task(minted, base)
  } finally {
    await revoke()
  }
}

/** A browser holding the session. Chrome as installed, else Playwright's own (`playwright-core install chromium`). */
async function signedIn(minted: Minted, base: string, run: (page: Page, context: BrowserContext) => Promise<void>) {
  let browser: Browser
  try {
    browser = await chromium.launch({ channel: 'chrome' })
  } catch {
    browser = await chromium.launch().catch(() => {
      throw new Error('no browser: install Google Chrome, or `pnpm exec playwright-core install chromium`')
    })
  }
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, locale: 'en-US' })
    await context.addCookies([
      {
        name: minted.name,
        value: minted.value,
        url: base,
        httpOnly: true,
        secure: base.startsWith('https://'),
        sameSite: 'Lax',
        expires: Math.floor(new Date(minted.expiresAt).getTime() / 1000),
      },
    ])
    const page = await context.newPage()
    page.on('pageerror', (error) => process.stdout.write(`page error: ${error.message}\n`))
    await run(page, context)
  } finally {
    await browser.close()
  }
}

/** Opens each page and says what it showed: where it landed, its title, its text. */
async function open(paths: string[]) {
  if (paths.length === 0) fail('open: which page? (/admin/events)')
  await withSession((minted, base) =>
    signedIn(minted, base, async (page) => {
      for (const [index, path] of paths.entries()) {
        const response = await page.goto(new URL(path, base).href, { waitUntil: 'networkidle' })
        const landed = new URL(page.url())
        process.stdout.write(`\n== ${path} → ${response?.status() ?? '?'} ${landed.pathname}${landed.search}\n`)
        if (landed.pathname === '/login') process.stdout.write('REFUSED: the panel sent this session to the login\n')
        process.stdout.write(`title: ${await page.title()}\n`)
        const text = await page.locator('body').innerText()
        const chars = Number(values.chars) || 3000
        process.stdout.write(`${text.slice(0, chars)}${text.length > chars ? `\n… (${text.length - chars} more characters)` : ''}\n`)
        if (values.shot) {
          const file = paths.length > 1 ? values.shot.replace(/(\.png)?$/, `-${index + 1}.png`) : values.shot
          await page.screenshot({ path: file, fullPage: true })
          process.stdout.write(`screenshot: ${resolve(file)}\n`)
        }
      }
    }),
  )
}

/** Hands a signed-in page to the agent's own Playwright steps. */
async function run(script: string | undefined) {
  if (!script) fail('run: which script? (a .mjs file exporting a default async function)')
  const steps = (await import(pathToFileURL(resolve(script)).href)) as {
    default: (signedIn: { page: Page; context: BrowserContext; base: string; write: boolean }) => Promise<void>
  }
  await withSession((minted, base) =>
    signedIn(minted, base, (page, context) => steps.default({ page, context, base, write: minted.write })),
  )
}

/** curl with the cookie, which reaches it through stdin (`-H @-`), never through its arguments. */
async function curl(path: string | undefined, options: string[]) {
  if (!path) fail('curl: which path? (/api/trpc/…)')
  await withSession(
    (minted, base) =>
      new Promise((done, failed) => {
        const child = spawn('curl', ['-sS', '-H', '@-', ...options, new URL(path, base).href], {
          stdio: ['pipe', 'inherit', 'inherit'],
        })
        child.stdin.end(`Cookie: ${minted.name}=${minted.value}\n`)
        child.on('error', failed)
        child.on('close', (code) => (code === 0 ? done() : failed(new Error(`curl exited ${code}`))))
      }),
  )
}

const COMMANDS: Record<string, () => Promise<void>> = {
  open: () => open(targets),
  run: () => run(targets[0]),
  curl: () => curl(targets[0], targets.slice(1)),
  list: async () => void process.stdout.write(await agentSession(['list'])),
  revoke: async () => void process.stdout.write(await agentSession(['revoke', '--all'])),
}
const chosen = command ? COMMANDS[command] : undefined
if (!chosen) fail('usage: pnpm agent:admin open|run|curl|list|revoke (see docs/agent-sessions.md)')
// A failure is said once the session is revoked (`withSession`'s finally), so the process ends here.
await chosen().catch((error: unknown) => fail(error instanceof Error ? error.message : String(error)))
