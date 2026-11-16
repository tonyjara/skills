# Drafting, and filing in Platypost

## Read first

1. `get_strategy` for the config's asset: the posting plan, voice and caption
   rules. It wins over everything below except a playbook's hard limits.
2. `get_playbook` with the asset id: every platform it posts to, with limits.
3. `list_channels` for the asset: which channels exist and their ids.
4. With no strategy, the fallback file in the config (voice, story lines,
   platform roles). Say once in the reply that the drafts used the fallback.

## Voice

- English, first person singular, the owner talking to another builder.
- Plain words, short sentences, the point first. No emojis, no hype words
  (game-changer, insane, 10x, revolutionary, excited to announce), no
  engagement bait ("thoughts?", "RT if", "like if"), no hashtag walls (one at
  most, usually none).
- Specific beats general: the number, the file, the one sentence that changed.
- Honest: what broke and what it cost is part of the story. Never claim more
  than the source says; "an agent built it" only when an agent did.
- No links in the main X post (they cost reach and money); put "link in reply"
  only when the post's job is the click.
- Name the owner's products when it helps; never explain them like an ad.

## Per platform

**X** (main channel)
- One post: the hook in the first line, the payoff by the end, at most 280
  characters unless the strategy says the account writes long posts.
- A thread only when the story has 3 to 6 real beats: post 1 must stand alone
  and make people open it; each next post one beat; the last one the lesson or
  the number. Number them `1/5`. Platypost has no thread field: put the posts
  in the body separated by a blank line and a line `---`, and write "Thread:
  post by hand, split at ---" in the notes.

**Bluesky**
- Its own text, at most 300 characters (graphemes). Same voice, slightly more
  conversational; not the X post cut short. No thread unless asked.

**Threads** (when the asset posts there)
- The Bluesky text usually fits (500 characters). Write its own only when the
  Bluesky one reads clipped.

**LinkedIn** (when it would interest a client or an employer)
- 600 to 1,300 characters. Lead with the problem a business would recognise,
  then what was done and what it showed, then one line on what it means for
  someone hiring. No "I'm thrilled", no broetry of one-line paragraphs, no
  hashtags beyond three at the end, and only if the strategy wants them.

**YouTube idea** (when it is visual or has enough meat for 8 to 15 minutes)
- Title (under 60 characters, concrete, no clickbait the video doesn't pay).
- Hook: the first 15 seconds, what's on screen and what's said.
- 3 to 5 beats, each a line: what is shown, what is learned.
- What to record (screen, terminal, phone) and what must be blurred.
- Note if it also cuts into a Short.

## Filing

One Platypost post per drafted nugget. Held nuggets are not filed.

1. `create_post`:
   - `assetId`: the config's asset.
   - `title`: `BIP <MM-DD> #<n>: <headline>` (the run's date, the list number).
   - `body`: the X text (the thread, split by `---`, when it is one).
   - `status`: `draft`. No `scheduledAt`. No `campaignId`.
   - `channelIds`: leave out, so it fans out to every active channel.
   - `notes`: see below.
2. `get_post` for its targets, then `set_channel_text` on each target that
   needs its own text: Bluesky's version on the Bluesky target, Threads' (or
   Bluesky's) on Threads, LinkedIn's on a LinkedIn target. Leave X on the body.
3. A version with no channel on the asset (often LinkedIn and always the
   YouTube idea) goes in the notes.

The notes, plain text, in this order:

```
Build in public, run 2026-11-16 #3. Sources: KUR-288, kururu@b2ce01d, reports/browser-tools-trial.md
Check before posting: <anything the owner must confirm: a number, a name left out, a screenshot to crop>
Thread: post by hand, split at ---        (only for a thread)

LinkedIn:
<text>

YouTube idea:
Title: …
Hook: …
Beats: 1) … 2) … 3) …
Record: …
```

Never call `approve_post`, `mark_posted`, `run_scheduler_tick` or
`run_campaign`, and never set a status other than `draft` while filing.

If Platypost is unreachable, write the drafts to the run file anyway and say
in the reply that they are only there.

## The run file

`runs/<YYYY-MM-DD>.md` (add `-2`, `-3` for a second run that day): the window,
whether a strategy was used, then per idea its number, headline, sources,
Platypost post id, and every draft in full; then the held ones with why.

## The offered log

Append one JSON line per idea, drafted or held, to `offered.jsonl`:

```json
{"date": "2026-11-16", "run": "2026-11-16", "n": 3, "headline": "One sentence cut agent browser jobs from 2 min to 9 s", "sources": ["KUR-288", "kururu@b2ce01d", "~/Documents/Kururu/reports/browser-tools-trial.md"], "status": "filed", "post": "<platypost post id>"}
```

`status` is `filed`, `held`, `dry-run` (shown but not filed), or later
`dropped`, `scheduled`. `sources` use the same keys `gather.py` prints: card
codes, `<repo>@<short sha>`, and paths with `~`. `gather.py` reads them back to
tag what was offered. Update a line's status in place when the owner drops or
schedules it.
