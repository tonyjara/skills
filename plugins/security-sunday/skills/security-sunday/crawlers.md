# Crawlers: search engines reach every site

A security setting can lock Google out without anything else breaking. The site answers people,
the health URL answers 200, and Search Console only shows it weeks later. Pasapy, 2026-10-16 to
10-25: the cutover set Cloudflare's `ai_training: block`, and verified Googlebot and Bingbot got
403 on every page and sitemap. Since 2026-09-15 Cloudflare counts both as "mixed-purpose"
(search + training) crawlers, so blocking Training blocks them too. The check after the move
passed only because it sent a Googlebot user agent from the Mac. Cloudflare's bot rules act on
the verified bot, identified by its address, so **a spoofed user agent proves nothing**. Read
the logs.

The coordinator runs this every Sunday. A project agent runs it for its domain after a cutover:
a DNS move, a host that became proxied, or a new firewall or bot setting (SKILL.md step 8).

## The policy (the owner's decision, 2026-10-26)

- **Training crawlers are turned away:** `GPTBot`, `ClaudeBot`, `anthropic-ai`, `CCBot`,
  `Google-Extended`, `Applebot-Extended`, `meta-externalagent`, `FacebookBot`, `Bytespider`,
  `Amazonbot`, `cohere-training-data-crawler`, `AI2Bot`, `PanguBot`. Google-Extended and
  Applebot-Extended are robots.txt tokens only; Google and Apple crawl with Googlebot and
  Applebot.
- **AI search and assistant fetches are let in**, under the same rules as everyone:
  OAI-SearchBot, ChatGPT-User, Claude-SearchBot, Claude-User, PerplexityBot, Perplexity-User and
  the like. Facebook's link previews (`facebookexternalhit`) are not FacebookBot, and stay allowed.
- **Google and Bing always get through.**

The policy is enforced in two places, and both carry the same list:

- **Cloudflare:** every zone in the account has the custom rule "AI training crawlers: blocked…" →
  Block:

  ```
  ((cf.verified_bot_category eq "AI Crawler") or (http.user_agent contains "GPTBot") or … one per
  training user agent above, minus the two tokens …) and not (cf.client.bot and
  (http.user_agent contains "Googlebot" or http.user_agent contains "bingbot")) and not
  (http.request.uri.path eq "/robots.txt")
  ```

  The user agents are needed as well as the category: CCBot, Bytespider and Amazonbot come from
  addresses Cloudflare does not verify. robots.txt stays readable so a blocked bot can read why.
  The rule is on DNS-only zones too, so it already holds if one of them is later proxied.
- **Every app's robots.txt** disallows the list with `/`. pasapy, jajotopa, the three landings,
  fastermenu and subignite do it in `robots.ts`; holapy, platypost's landing and kururu's site in
  `public/robots.txt`; bytetify in `next-sitemap.config.js` (its robots.txt is generated at
  build). A new site gets the same group.

## 1. Cloudflare, every zone

Use the `cloudflare-api` MCP tools (`execute`). `GET /zones` lists the account's zones. Then, per
zone:

- **Settings.** `GET /zones/<id>/bot_management`: `ai_training` and `ai_bots_protection` must be
  `disabled`. `block` or `only_on_ad_pages` there is a finding, and so is `fight_mode: true`.
  `GET /zones/<id>/settings/security_level` must not be `under_attack`. The custom rules entry
  point (`GET /zones/<id>/rulesets/phases/http_request_firewall_custom/entrypoint`) holds the
  policy's rule, unchanged.
- **What Cloudflare can touch.** `GET /zones/<id>/dns_records`: only `proxied` hosts go through
  Cloudflare's rules. A DNS-only zone never shows up in its logs, so check its host instead
  (section 2). Proxied hosts on 2026-10-26: `pasapy.com`, `www` and `img`, `r2.fastermenu.com`,
  `r2-dev.fastermenu.com`, `media.holapy.com`, `img.tonyjara.com`, `casita.tonyjara.com`. A new
  one is a change: look at it.
- **The logs, for every zone with a proxied host,** since last Sunday (31 days are kept):

  ```graphql
  query($z: String!, $g: ZoneHttpRequestsAdaptiveGroupsFilter_InputObject!) { viewer { zones(filter: {zoneTag: $z}) {
    httpRequestsAdaptiveGroups(limit: 100, filter: $g, orderBy: [count_DESC]) { count dimensions {
      clientRequestHTTPHost edgeResponseStatus originResponseStatus securitySource securityAction userAgentBrowser } } } } }
  ```

  Use `$g = {datetime_geq: "<8 days ago>", verifiedBotCategory: "Search Engine Crawler", OR:
  [{userAgent_like: "%Googlebot%"}, {userAgent_like: "%bingbot%"}]}` and send it as
  `POST /graphql`. A row with a `securityAction` (block, challenge, managed_challenge) is a
  finding. So is a 403, 429 or 503 at the edge with `originResponseStatus: 0`, meaning
  Cloudflare answered by itself. 200s that are all `robots.txt` are not access: rules leave
  `robots.txt` open. Name the rule with `firewallEventsAdaptive` (same filter without the
  `OR`, `orderBy: [datetime_DESC]`, fields `datetime action source description ruleId
  rulesetId clientRequestHTTPHost clientRequestPath userAgent`).
- **The AI policy, in the same logs:** filter `OR: [{verifiedBotCategory_in: ["AI Crawler", "AI
  Search", "AI Assistant"]}, {userAgent_like: "%GPTBot%"}, …]`, with one entry per bot named in
  the policy. Group by `verifiedBotCategory userAgent edgeResponseStatus securityAction`. A
  training bot gets 403 (block) everywhere but `/robots.txt`. A search or assistant bot gets
  the site's own answer (200, 3xx, 404), never a block. A search or assistant bot showing up
  under "AI Crawler" is a finding: Cloudflare moved it, so add an exception for it to the rule.
- **API quirks.** One zone per query (`zoneTag_in` answers "too many zones requested"). Group
  ordering is `count_DESC` or `datetimeMinute_DESC`, never `dimensions_…`. Free zones lack
  `clientRequestQuery`. The analytics budget runs out after about ten queries ("Rate limiter
  budget depleted"): wait five minutes, and query only zones with a proxied host.

subignite.com is in another Cloudflare account (nameservers `karsyn`/`ridge`) that this
connection cannot read. Its records answer straight from Vercel (`server: Vercel`). If it ever
answers `server: cloudflare`, ask the user for access to that account.

## 2. Hosts that are not behind Cloudflare

- **Vercel:** for each project, `vercel -Q <config> --scope <team> api
  "/v1/security/firewall/config/active?projectId=<project>"`. The configs and teams are in
  `inventory.yaml`, and `vercel project ls --scope <team>` lists the projects. "Config not
  found (404)" means the defaults: no custom rules, no managed bot rulesets. A config is a finding if
  it has a custom rule that denies or challenges, or if `bot_protection` or `ai_bots` is on.
  Look at each one.
- **VPS:** a public Traefik router with an `ipAllowList` middleware (a Cloudflare-only list on
  a DNS-only host locks out everyone, Google included). `grep -l ipAllowList
  /etc/dokploy/traefik/dynamic/*.yml`, and each service's `traefik.http.routers.*.middlewares`
  label.

## 3. Fixing it

Keep the policy above whole:

1. If the zone lacks it, add the policy's WAF rule first, so training crawlers are never let in.
   Googlebot and Bingbot are "Search Engine Crawler". OAI-SearchBot and Exa are "Search Engine
   Crawler" too, and ChatGPT-User is "AI Assistant". None of them is matched.
2. `PUT /zones/<id>/bot_management` with the body `GET` returned, minus `using_latest_model`
   and `stale_zone_configuration`, and `ai_training: "disabled"`.
3. Prove it from the logs: the next real Googlebot request to a page (not `robots.txt`) gets
   200. Googlebot comes every 30 to 75 minutes. Search Console's URL Inspection → Test live URL
   is the user's instant check.
4. Tell the user what to do in Search Console: resubmit the sitemap, "Validate fix" on the
   "Blocked due to access forbidden (403)" issue, request indexing for the main pages, and the
   same in Bing Webmaster Tools.

A rule you did not write (a managed rule, someone else's custom rule) is reported before you
change it, unless it is this exact case.

## 4. Report

One row in the Sunday summary: every zone and host checked, the verified-crawler requests
blocked since last Sunday (0 is the answer), and anything fixed.
