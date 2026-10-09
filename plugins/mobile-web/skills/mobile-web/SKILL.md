---
name: mobile-web
description: Make a web app feel right on phones (Next.js, Tailwind v4, shadcn/Radix, or any stack) and prove it with screenshots. Covers locking the viewport scale, fields that do not trigger iOS zoom, safe-area insets, dialogs as bottom sheets, nav and tab rows that scroll instead of wrapping, tables that become cards, buttons whose labels wrap, compact phone spacing, and a headless-Chrome audit (scripts/mobile-shots.mjs) that signs in through the shared Mailpit, screenshots pages at phone width and reports anything wider than the screen and any field iOS would zoom into. Load this whenever a page, panel, dashboard, form, table or dialog looks bad, cramped, zoomed, cut off or overflowing on a phone; whenever someone says mobile, responsive, iPhone, Android, Safari, touch, pinch, safe area, or "make it work on my phone"; and before shipping any web UI that people will open on a phone, even if they only ask to "check the layout".
---

# Mobile web: making a web panel feel like an app on a phone

The failures are always the same family: the page is wider than the screen, text runs
out of its box, tapping a field zooms the page, a centred modal is taller than the
viewport, a 7-column table scrolls sideways under a thumb, the nav takes a third of the
screen. Most of them come from desktop assumptions baked into shared primitives, so the
fix lives in the primitives (button, input, dialog, tabs, table, shell), not in pages.

## Workflow

1. **Audit before touching anything.** Run the audit script (below) over every page and
   the dialogs with `--label before`, read the screenshots at 390px, and read its report.
   It tells you which element is wider than the viewport, which text spills its box and
   which fields iOS will zoom into, so you fix causes instead of symptoms. Keep the
   "before" shots to compare.
2. **Fix in the primitives first** (viewport, fields, buttons, dialog, tabs, table, shell,
   spacing tokens), then the handful of pages with their own layout bugs.
3. **Re-run the audit with `--label after` at 390 and 360 wide, then once with
   `--desktop`** (1280) so the desktop did not change. "Done" means: `scrollWidth ===
   viewport` on every page, no text overflow, no field under 16px, every dialog fits and
   scrolls inside, and the desktop screenshots look as before.

## The audit script

`scripts/mobile-shots.mjs`, in this skill's folder (the base directory shown when the
skill loads), drives a real headless Chrome over the DevTools protocol with no
dependencies (Node 22+ for the built-in WebSocket). Run it from the project's root by its
full path; do not copy it into the project, so a fix to the script reaches every project.
It emulates a phone (device scale 2, touch, iPhone user agent), can sign in, clicks
through dialogs, and for each page saves a PNG and prints the viewport width, the
document `scrollWidth`, every element whose right edge passes the viewport or whose text
is wider than its own box, and every text field under 16px.

```bash
S=<this skill's folder>/scripts/mobile-shots.mjs
node $S --login admin@example.com --label before --full   # sign in once, shoot the pages
node $S --label before --width 360 --height 640            # same session, a smaller phone
node $S --label after --desktop                            # the desktop regression pass
```

### Setting up a project

A project keeps a `mobile-shots.json` at its root, committed: where its dev server runs,
how to sign in, and the pages to shoot, so a run needs no flags and "before" and "after"
cover the same pages. Flags override it; every key is optional. Add `/mobile-shots/` (the
screenshots) to `.gitignore`.

| key | default | what it is |
|---|---|---|
| `base` | `BETTER_AUTH_URL` from the environment, `.env.local` or `.env`; else `http://localhost:3000` | the dev server, on the project's own port (`--base`) |
| `pages` | none | paths to shoot, with steps (below); paths on the command line replace them |
| `mailTag` | `name` in `package.json`, without its `@scope/` | the project's `X-Tags` value in the shared Mailpit (`--mail-tag`) |
| `login.path` | `/api/auth/sign-in/magic-link` | where `--login` asks for a sign-in link |
| `login.body` | `{ "email": "{email}", "callbackURL": "{next}" }` | the JSON posted there; `{email}` and `{next}` are filled in |
| `login.next` | `/` | where the link lands (`--next`) |
| `login.link` | `magic-link/verify` | a regex the sign-in URL in the mail matches |
| `mailpit` | `http://127.0.0.1:8025` | the shared inbox (`--mailpit`) |
| `out` | `mobile-shots` | where the shots go (`--out`) |
| `profile` | one folder per project in the system temp dir | Chrome's profile, which keeps the session (`--profile`) |

The defaults fit an app that signs in with Better Auth's magic-link plugin and tags its
development mail with its slug (the `auth-like-tony` skill), so such a project usually
needs only `pages`. Example, for an app that requests its links through its own tRPC
route instead (Jajotopa):

```json
{
  "base": "http://localhost:3000",
  "mailTag": "jajotopa",
  "login": {
    "path": "/api/trpc/auth.requestMagicLink",
    "body": { "json": { "email": "{email}", "next": "{next}" } },
    "next": "/admin"
  },
  "pages": ["/admin", "/admin/visitas", "/admin/visitas|click=Nueva visita"]
}
```

### Running it

- Each page is a path plus optional steps separated by `|`: `click=<visible text>` (first
  button/link/tab whose text starts with it), `wait=<ms>`, `scroll=<px>`, `eval=<js>` (no
  `|` inside the expression).
- `--full` captures the whole document; leave it off for dialogs (what matters is whether
  the sheet fits the viewport). `--width/--height` default to 390×844; also run 360×640.
  `--desktop` turns phone emulation off and defaults to 1280×800.
- Shots land in `mobile-shots/<label>-<width>[-desktop]/`, with `report.json` beside them.
  `--strict` exits 1 when a page is wider than the screen or has a field under 16px.
- **Signing in.** `--login <email>` posts `login.body` to `login.path`, waits up to 30s
  for a mail in the shared Mailpit that is tagged with the project's `mailTag`, addressed
  to that email and received after the request, and opens the sign-in link in it. The
  tag is there because every project on the machine sends to the same Mailpit; the time
  because the inbox still holds older, used links to the same address, and a mail sent
  by a background worker can arrive after them. A link built for another host
  (`127.0.0.1`, a Tailscale address) is opened on `base`'s origin, so the session cookie
  lands where the pages are shot.
- The profile keeps the session between runs: sign in once, then run without `--login`.
  Use a throwaway profile for signed-out pages: `--profile "$(mktemp -d)"`.
- An app that signs in some other way: `--cookie name=value` (repeatable) with a session
  you already have. Never put a cookie in `mobile-shots.json`.
- Chrome comes from `$CHROME`, else the usual install paths (Chrome, Chromium, Edge,
  Brave).

### Reading the report

- `spills` entries inside a container that is meant to scroll sideways (a `scroll-row`
  nav, a table wrapper) are expected; the page-level `scrollWidth` is the number to watch.
- `text` is a leaf element whose text is wider than its own box: a label running out of
  a button, an email or URL that cannot break.
- `zoom` is a text field under 16px on a phone (see Fields).
- `viewport meta` is printed for the first page and whenever a page differs; compare it
  with Viewport and zoom below.

Before driving a server, check what listens on its port (`lsof -i :<port>`, `ps`): it must
be this project's dev server, not another project's, and never a `dev:prod`-style process
that talks to production. Signing in and clicking through dialogs there touches real data.

## What to fix, and why

### Viewport and zoom

Export a viewport from the root layout: `width=device-width, initial-scale=1,
maximum-scale=1, user-scalable=no, viewport-fit=cover, interactive-widget=resizes-content`
plus a `theme-color` matching the page background. Locking the scale makes the panel
behave like an app (no accidental pinch, no double-tap zoom) and, together with 16px
fields, stops iOS Safari zooming into a focused input. `viewport-fit=cover` is what makes
`env(safe-area-inset-*)` non-zero; without it the insets are always 0. `resizes-content`
makes Android shrink the layout viewport for the keyboard, so `100dvh` and a bottom sheet
stay above it. Note that iOS ignores `user-scalable=no` for pinch (accessibility) but
honours `maximum-scale` for the focus zoom; a user who needs zoom still has it there.

Next.js: `export const viewport: Viewport = { width: "device-width", initialScale: 1,
maximumScale: 1, userScalable: false, viewportFit: "cover", interactiveWidget:
"resizes-content", themeColor: "…" }` in `app/layout.tsx`. Any other stack: the same
values in `<meta name="viewport" content="…">` and `<meta name="theme-color" content="…">`.

Add `touch-action: manipulation` to everything pressable (a, button, input, select,
textarea, label, summary, role=button/tab/menuitem): no double-tap zoom and no tap delay on
them, whatever the viewport says. Tailwind's preflight already clears the tap highlight.

### Fields

Any input, textarea or select below 16px makes iOS Safari zoom the page when it gets
focus, and it does not zoom back. Set `text-base sm:text-sm` on the primitives (and on a
select trigger, so it matches) so phones get 16px and desktops keep the compact size. Keep
controls at least 40px tall (44px is Apple's guideline; 40 is the usual shadcn `h-10` and
acceptable). Limit popovers to the space Radix reports:
`max-h-[min(24rem,var(--radix-select-content-available-height))]`.

### Buttons and text

A button with `whitespace-nowrap` and a fixed `h-10` cannot shrink below its label, so a
long label (a translation, a name) in a narrow column runs out of the box or pushes the
row sideways. Make labels wrap instead: drop `whitespace-nowrap`, use minimum heights with
vertical padding, `text-center` and `max-w-full` on the base, and keep the icon size fixed.
Example, shadcn's `buttonVariants` sizes:

```ts
size: {
  default: "min-h-10 px-5 py-2",
  sm: "min-h-9 px-3 py-1.5",
  lg: "min-h-12 px-7 py-2",
  icon: "size-10 shrink-0 p-0",
},
```

Put `overflow-wrap: break-word` on `body` as a safety net for emails and URLs, and
`wrap-anywhere` on the specific lines that show them (Tailwind 4.1+). Avoid
`overflow-wrap: anywhere` globally: it changes min-content sizing and lets table columns
and flex items collapse to one character per line.

### Layout

- **A grid column takes the width of its widest child's min-content**, so a table inside
  `grid lg:grid-cols-[2fr_1fr]` widens the column past the screen even when the table's
  own wrapper is `overflow-x-auto`. Use `minmax(0, …)` tracks
  (`grid-cols-[minmax(0,1fr)] lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]`) or `min-w-0`
  on the grid item. The same applies to flex children: `min-w-0` lets them shrink.
- **Rows that wrap into three lines (nav pills, tabs, filter chips) cost a third of the
  screen.** Make them one row that scrolls sideways on phones and wraps from `sm:`.
  Tailwind v4 utility (globals.css):
  ```css
  @utility scroll-row {
    display: flex; flex-wrap: nowrap; overflow-x: auto;
    overscroll-behavior-x: contain; scroll-snap-type: x proximity; scrollbar-width: none;
    &::-webkit-scrollbar { display: none; }
    & > * { flex-shrink: 0; scroll-snap-align: start; }
  }
  ```
  `overflow-x: auto` clips vertically too, so if the items cast a shadow, give the row a
  `padding-bottom` of the shadow's offset or the active item's shadow is cut off.
  Use it as `scroll-row -mx-4 px-4 sm:mx-0 sm:px-0 sm:flex-wrap sm:overflow-visible`
  (`-mx-4 px-4` being the page gutter): the negative margin bleeds the row to the screen
  edge so items scroll under the gutter instead of being cut at it. Reveal the active
  item on mount by scrolling only the container (never `scrollIntoView`, which also
  scrolls the page), and only when the active element changed, so a re-render mid-swipe
  does not snap back. React:
  ```ts
  /** Keeps the item matching `selector` in the middle of a sideways-scrolling row. */
  export function useRevealActive<T extends HTMLElement>(selector: string) {
    const ref = useRef<T>(null);
    const shown = useRef<Element | null>(null);
    useEffect(() => {
      const list = ref.current;
      const active = list?.querySelector<HTMLElement>(selector) ?? null;
      if (!list || active === shown.current) return;
      shown.current = active;
      if (!active || list.scrollWidth <= list.clientWidth) return;
      const offset = active.getBoundingClientRect().left - list.getBoundingClientRect().left;
      list.scrollLeft += offset - (list.clientWidth - active.offsetWidth) / 2;
    });
    return ref;
  }
  ```
  Use it as `const ref = useRevealActive<HTMLElement>('[aria-current="page"]')` on the
  nav, or `'[data-state="active"]'` on a Radix tab list. Above a dozen options
  (categories, types) use a `Select` on phones instead.
- **Tables become cards below `sm:`.** A 6-column table that scrolls sideways hides the
  status and the actions behind a swipe nobody discovers. Render the same column
  definitions as a stacked list: the first column is the card title, every other column
  a label/value line (`dl` with `grid-cols-[auto_minmax(0,1fr)]`, header text as the
  label), action columns at the bottom with no label, and a per-column setting to adjust
  (with TanStack Table, `meta.mobile: "title" | "actions" | "hidden"`). Keep the search
  box and pagination shared; sorting stays at the default on phones. Give the loading
  skeleton the same two shapes (`sm:hidden` card list, `hidden sm:block` table) so
  nothing jumps when data arrives.
- **Stat cards two per row** on phones (`grid-cols-2`, odd last card `col-span-2`),
  smaller number (`text-3xl sm:text-4xl`); five full-width cards push the content a whole
  screen down.
- **Phone-shaped previews, maps, charts**: `w-full max-w-[380px]`, never a fixed width.

### Dialogs and alert dialogs

A centred modal with `translate(-50%, -50%)` and no max height is cut off on a phone as
soon as the form is tall, and the keyboard covers its lower half. On phones make it a
bottom sheet, which is where the thumb and the keyboard are, and keep the centred box from
`sm:`. Radix/shadcn `DialogContent` classes, mobile first, then `sm:` restores the desktop
(`pb-safe-4` is from Safe areas below):

```
fixed z-50 grid w-full gap-4 border bg-background shadow-lg duration-200
data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=open]:fade-in-0 data-[state=closed]:fade-out-0
inset-x-0 bottom-0 max-h-[calc(100dvh-3rem)] overflow-y-auto rounded-t-lg border-b-0 p-4 pb-safe-4
data-[state=open]:slide-in-from-bottom-8 data-[state=closed]:slide-out-to-bottom-8
sm:inset-x-auto sm:bottom-auto sm:top-[50%] sm:left-[50%] sm:max-h-[calc(100vh-2rem)] sm:max-w-lg
sm:translate-x-[-50%] sm:translate-y-[-50%] sm:rounded-lg sm:border-b sm:p-6
sm:data-[state=open]:slide-in-from-bottom-0 sm:data-[state=closed]:slide-out-to-bottom-0
sm:data-[state=open]:zoom-in-95 sm:data-[state=closed]:zoom-out-95
```

Border, radius and shadow are the kit's own (stock shadcn tokens above); what matters is
the positioning, the heights and the per-breakpoint animation. A theme with hard offset
shadows keeps the shadow to `sm:`: a sheet against the screen edge has nowhere to cast it.

`100dvh` follows the Android keyboard with `interactive-widget=resizes-content`; iOS
keeps the layout viewport and scrolls the focused field into view itself. Once the base
handles height, remove per-dialog `max-h-[90vh] overflow-y-auto` overrides. Footers stack
`flex-col-reverse` on phones so the primary action is nearest the thumb. Apply the same
classes to the alert dialog; a confirmation is still better at the bottom.

### Safe areas

With `viewport-fit=cover` the page runs under the rounded corners, the notch (landscape)
and the home bar. Functional Tailwind v4 utilities keep that readable:

```css
@utility pt-safe-* { padding-top: calc(--value(integer) * var(--spacing) + env(safe-area-inset-top, 0px)); }
@utility pb-safe-* { padding-bottom: calc(--value(integer) * var(--spacing) + env(safe-area-inset-bottom, 0px)); }
@utility px-safe-* { padding-left: max(calc(--value(integer) * var(--spacing)), env(safe-area-inset-left, 0px));
                     padding-right: max(calc(--value(integer) * var(--spacing)), env(safe-area-inset-right, 0px)); }
```

Use them where the layout touches an edge: the header (`pt-safe-0`, `px-safe-4`), the
main column (`pb-safe-6`, `px-safe-4`), the bottom sheet (`pb-safe-4`), the auth card,
sticky footers, and toasts (with Sonner, `mobileOffset={{ top: "max(1rem,
env(safe-area-inset-top))", left: "1rem", right: "1rem" }}` on the `Toaster`, with the
toast `w-full` instead of a fixed `w-[356px]`). Insets are 0 on desktops and in portrait
Safari's top, so nothing changes there. Avoid `pb-safe-6` next to `py-6` on the same
element: both set padding-bottom and the winner depends on utility order; write `pt-6
pb-safe-6`.

### Density and the header

Phones lose vertical space fast. In one panel, a header with logo, name, a labelled
sign-out button and a wrapped nav took 200 of 844 pixels; after the pass it took 100. Make
the sign-out button icon-only below `sm:` (keep `aria-label` and `title`), hide the user's
name and role label below `sm:`, tighten `py-4` to `py-3`, main `py-8` to `pt-6`. Define a
spacing token for card padding instead of `p-5` everywhere: `--spacing-card: clamp(1rem,
4vw, 1.25rem)` in `@theme inline` gives `p-card`, `px-card`, `gap-card` that scale on
their own and still get overridden cleanly by `p-0`. Page headers `mb-6 sm:mb-8`.

### Touch details

- Row click handlers on cards too, with buttons and links inside excluded
  (`event.target.closest("a, button, input, …")`).
- Maps (Leaflet, Mapbox, Google Maps) capture the drag and trap page scrolling; on touch
  devices either turn dragging off until the user taps the map, or use the library's
  cooperative gestures. Say so in the recap if left as is.
- Hover-only affordances (`hover:underline` on sortable headers) need a visible resting
  state on phones; the card layout usually removes the problem.

## Finish the task

Tell the person what the audit found before and after (which pages overflowed, which text
spilled, which fields zoomed, what the dialogs did), what changed in the primitives versus
in pages, and what was left (maps, anything that needs real device testing such as the iOS
keyboard behaviour and standalone/home-screen mode). Point them at the "before" and
"after" screenshots (`mobile-shots/before-390/`, `mobile-shots/after-390/`, …) and leave
the project's `mobile-shots.json` with the pages that were audited, so the next pass shoots
the same ones.
