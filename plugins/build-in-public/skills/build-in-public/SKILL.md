---
name: build-in-public
description: Build-in-public digest for a solo builder's personal brand. Mines what was shipped in a window (today, yesterday, the last few days, the week) from kururu's cards, git commits across the project folders and the reports and research notes; optionally only the projects the owner names; picks the 5 to 8 nuggets a builder audience would care about, spread across every project worked on; drops or anonymizes anything about clients, other people, production data or security; drafts an X post or thread, Bluesky, LinkedIn and a YouTube idea for each; files them as unscheduled Platypost drafts on the owner's personal asset; and replies with a numbered, phone-sized list the owner can act on ("schedule 2 and 4", "rewrite 3"). Use it whenever the owner says "post ideas from today", "from this week", "what can I post", "build in public", "content from what we shipped", "anything worth tweeting", "post ideas from Pasapy and Tile Bandit this week", or asks for a digest of the day's work for social media, and for the follow-ups on a list it produced.
---

# Build in public

The owner builds products with AI agents and wants a steady flow of honest
posts about it without stopping to write them. You know what was shipped; your
job is to turn that into a short list of good post ideas with drafts ready to
edit, copy or schedule. You draft. The owner decides what goes out.

## Hard rules

- **Never publish, approve or mark a post posted.** Drafts only: no
  `approve_post`, no `mark_posted`, no status `approved` or `published`, no
  `scheduledAt` unless the owner asks to schedule that post.
- **Privacy wins over a good story.** Clients, end users, people, production
  data, secrets, security internals and unannounced deals never appear. When in
  doubt, flag the nugget instead of drafting it. See
  [references/nuggets-and-privacy.md](references/nuggets-and-privacy.md).
- **Nothing invented.** Every number, quote and claim in a draft comes from a
  card, a commit or a report you read. If a detail is missing, leave it out.
- **Replies fit a phone.** The owner often reads this on Telegram.

## Files

The owner's own settings live outside this skill, in
`~/Documents/Kururu/build-in-public/` (on another setup, ask where):

| file | what |
|---|---|
| `config.md` | the Platypost asset, project roots, docs folders, and which projects are own, private or unknown |
| `offered.jsonl` | one line per idea ever offered, so a run never repeats one |
| `runs/<YYYY-MM-DD>[-n].md` | each run's list and full drafts, with Platypost post ids |

Read `config.md` first. If it is missing, ask for the asset and the client
names before drafting anything, and write it from
[references/config-template.md](references/config-template.md).

## The run

### 1. Gather the window

**When.** Default: yesterday and today. "Today" is today; "this week" or
"week" is the last 7 days; "since Thursday" or a date range is that. Local
time.

**Which projects.** A bare request covers everything worked on in the window.
When the owner names projects ("post ideas from Pasapy and Tile Bandit this
week"), pass each as `--project`: only those workspaces and repos, plus
profile-board cards and docs that mention them. Use the names the owner uses;
the script says when one matches nothing and lists the names it knows, so
pick the right one or ask. Naming a client's project does not lift the
privacy filter: its nuggets are still told generically or held.

```sh
python3 <skill>/scripts/gather.py --window recent    # today | yesterday | recent | week | 3d
python3 <skill>/scripts/gather.py --since 2026-11-13 --until 2026-11-16
python3 <skill>/scripts/gather.py --window week --project pasapy --project "tile bandit"
python3 <skill>/scripts/gather.py --card KUR-288     # one card whole
```

It prints, read-only: kururu cards that moved to done or review in the window
(from kururu's database), commits in every repo under the config's roots, and
the reports and research notes changed. Items are tagged `[private: X]` or
`[private: X?]` (unknown owner) from the config, and `[offered …]` when an
earlier run already used them.

When the database is not readable (another node, a changed schema), use Kuru's
tools: `kururu_status` for the workspaces (only the asked projects', if any),
`cards` with `column: "done"` and `column: "review"` for each, `card_history`
for when a card moved, and `search` for a decision or a quote you half
remember. `cards` with `card` reads one card whole.

### 2. Find the nuggets

Every project is fair game: a calendar fix in an events app, a window
manager's edge case or a home-PC video job can each make a better post than
the obvious one. Read past the titles for the candidates: the card body,
`git show <sha>` for the commit message, a report a card points to. The story
is usually in the "why" and the numbers, not the title.

Pick 5 to 8, ranked by the rubric in
[references/nuggets-and-privacy.md](references/nuggets-and-privacy.md): how
good the nugget is, never which project it came from. Spread them across the
projects worked on; two from one project only when both are strong, and the
project with the most commits does not get the most ideas by default. Skip
anything tagged `[offered …]` unless there is real news on it (say so in its
line). A thin window gives fewer ideas; never pad the list.

### 3. Filter for privacy

Apply the filter in the same reference to every pick and to every sentence of
every draft. Anonymize what can be told generically ("a client's WhatsApp
ordering bot"), drop what cannot, and list the borderline ones as **held**
with one line saying why, undrafted.

### 4. Draft

First read the asset's `get_strategy` and `get_playbook` (Platypost). The
strategy wins over a playbook's advice; a playbook's hard limits always hold.
If the asset has no strategy yet, use the voice in the file the config names
as fallback, and say so in the reply once. A strategy or fallback's story
lines shape how a post is framed, not which nuggets are picked.

Per nugget, by the rules in
[references/drafting-and-filing.md](references/drafting-and-filing.md):

- **X**: one post, or a 3 to 6 post thread when the story earns it.
- **Bluesky**: its own version, 300 characters.
- **LinkedIn**: when it would interest a client or employer.
- **YouTube**: an idea (title, hook, 3 to 5 beats) when it is visual or meaty.

English, first person, plain, no emojis, no hashtags beyond one, no hype.

### 5. File in Platypost

One draft post per nugget on the config's asset, unscheduled, status `draft`,
with each channel's own text and the rest in the notes. The exact calls are in
[references/drafting-and-filing.md](references/drafting-and-filing.md).
Write the run file, then append one line per idea (held ones too) to
`offered.jsonl`.

### 6. Reply

A numbered list, one line per idea, then one line on where the drafts are and
one on what was held:

```
Post ideas, Nov 15–16, all projects (6), in Platypost › Tony Jara as drafts "BIP 11-16 #n":
1. One sentence cut agent browser jobs from 2 min to 9 s · X thread, Bsky, LI, YT
2. iPhone Mirroring reports the wrong safe area · X, Bsky, YT
3. …
Held: home network work (security); a client's go-live (names a client).
Say "schedule 2 and 4", "rewrite 3 shorter", or "drop 5".
```

Each line: the hook in under about 60 characters, then the formats drafted.
No links, no ids, no paragraphs. The run file has the full text if asked.

## Follow-ups

Find the run by date (the latest run unless the owner names one) and the post
by its number in the run file.

- **"schedule 2 and 4"**: set `scheduledAt` with `update_post` at the time the
  owner gives, else the strategy's next free slot for that platform, else ask.
  Leave the status as scheduling sets it; never approve. Manual channels then
  wait in the Today queue for the owner to post by hand.
- **"rewrite 3"** (shorter, punchier, more technical, …): rewrite with
  `update_post` and `set_channel_text`, show the new X text in the reply.
- **"drop 5"**: `delete_post` on that draft, and mark it `dropped` in
  `offered.jsonl` so it is not offered again.
- **"more like 2"**: look again in the same window for that kind of nugget.
- **"more from Tile Bandit"**: run again on the same window with
  `--project`, skipping what was offered.
- **"post 3 now"** or **"approve 3"**: refuse kindly and say how to do it in
  Platypost; this skill never publishes or approves.
