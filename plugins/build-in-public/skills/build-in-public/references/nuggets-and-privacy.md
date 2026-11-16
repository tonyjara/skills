# Finding nuggets, and the privacy filter

## What makes a nugget

The audience is other builders: developers, indie founders, people using AI
coding agents. They stop scrolling for something they did not know, a number
they can compare with their own, or an honest story. They scroll past
changelogs, "excited to announce" and generic tips.

Good, roughly in this order:

1. **A surprising cause.** A bug whose cause nobody would guess: the simulator
   never showed it, the tool lied, the fix was one line after a day.
2. **A number from a real measurement.** Before/after, a trial with a table,
   cost per job, time saved, "17 of 21 runs did X".
3. **An AI-agent workflow insight.** How agents were briefed, what they got
   wrong, what one sentence in a brief changed, how many ran overnight and what
   came out.
4. **A design decision with a tradeoff.** What was chosen, what it cost, what
   was given up.
5. **A failure told honestly.** What broke, what it cost, what changed.
6. **A shipped feature** that a builder can picture, told by the problem it
   solves, not by its name.
7. **A before/after** that would work as a screenshot or a clip.

Score each candidate on three things only: surprise (would a builder learn
something), proof (a number, a diff, a screenshot to show), and safety (how
much privacy work it needs). Which project it came from, and whether it fits a
story line, are not in the score.

### Every project counts

All the projects are fair game, and you never know which one holds the post
that travels: an events app's calendar edge case, a window manager's bug, a
video job on a home PC, a marketplace's money flow, a smart-home script.
Spread the list across the projects worked on in the window:

- One idea per project first, from each project with a nugget worth one; a
  second from the same project only when it beats every remaining candidate
  elsewhere.
- Volume is not merit. A project with fifty commits gets no more ideas than
  one with three unless its nuggets are better.
- A client's project counts too, but only as what the filter below allows:
  told generically, or held.
- When the owner names projects, spread within those.

### Story lines are framing, not a filter

The brand research (and later the asset's strategy) names story lines, such
as AI coding agents in daily use and payments and invoicing in a small
country. Use them to frame a post: many nuggets from any project are also an
agent story (how agents built, tested or broke it) or a small-country story
(a local payment network, a city's spelling, weak signal at a venue's door).
Never use them to rank one project's nugget over another's. Tell
infrastructure and compliance as a builder's story, not a schema walkthrough.

### Where nuggets hide

- **Commit messages** in these repos are long and say why. The subject line
  often holds the whole story ("the hint is read when first asked for, not at
  import, because…"). `git show <sha> --stat` for its size.
- **Card bodies** hold the owner's own words ("the owner, 2026-11-14: …"), the
  options considered and the constraints. Quote the owner only if the quote is
  about the work and names nobody.
- **Reports** have the numbers and the conclusion at the top.
- **Clusters**: many cards done in one night on one project is itself a story
  (what agents built while the owner slept), told with times and counts.

## The privacy filter (hard)

Run it on every pick and every sentence of every draft. If a draft would only
work with a private detail in it, hold it.

**Never in a draft:**

- **Clients and their projects by name**, or anything that identifies them
  (their domain, their product's name, their city plus their trade). The
  config's Private list names them. A project marked `?` is unknown: treat it
  as private and ask the owner once whether it is theirs.
- **End users and customers**: names, numbers, handles, emails, messages,
  orders, what they bought or said, even paraphrased.
- **Other people**: testers, collaborators, friends, family, by name or role
  that identifies them, including people invited to a TestFlight or added to a
  team. "A friend tested it" is fine; who is not.
- **Production data**: counts of a client's customers or orders, revenue that
  is not the owner's own and shared by them, database contents, real records.
- **Secrets and security internals**: keys, env var values, team ids, account
  ids, hostnames and IPs, ports, tunnels' names, how auth or a session is
  minted, firewall and network layout, home devices, anything an attacker
  could use. "I keep agents off production" is fine; how, in detail, is not.
- **Unannounced things**: products not launched (the config says which), deals,
  pricing talks, partners, vendors' account status, legal questions still
  open.
- **Other companies' content**: scraped or copied listings, a competitor's
  material, anything that suggests taking it.

**Fine:**

- The owner's own products by name (the config's Own list), their own code,
  their tools, their machines in general terms.
- A client project told generically, when nothing in it identifies the client:
  "a client's WhatsApp ordering bot", "a local delivery business", with no
  name, place, numbers or screenshot of their data.
- Numbers from the owner's own measurements and own products.
- Public tools and vendors by name when the post is about the tool (Playwright,
  ffmpeg, Expo, Claude Code), without account details.

**Hold, don't draft** (list under "Held" in the reply, one line why):

- It names or would identify a client, a person or an unannounced product, and
  cannot be told without that.
- It touches security, money held for others, legal or tax questions still
  open, or the owner's home.
- You are not sure whether a project is the owner's.

Screenshots, clips and diffs suggested for a post follow the same rules: say
what must be cropped or blurred, or don't suggest one.
