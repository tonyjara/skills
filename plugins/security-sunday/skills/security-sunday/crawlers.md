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

## 1. Cloudflare, every zone

Use the `cloudflare-api` MCP tools (`execute`). `GET /zones` lists the account's zones. Then, per
zone:

- **Settings.** `GET /zones/<id>/bot_management`: `ai_training` and `ai_bots_protection` must be
  `disabled`. `block` or `only_on_ad_pages` there is a finding, and so is `fight_mode: true`.
  `GET /zones/<id>/settings/security_level` must not be `under_attack`.
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

The owner wants AI training crawlers blocked and search engines let in. Keep both:

1. Add a WAF custom rule on the zone: `(cf.verified_bot_category eq "AI Crawler")` → Block.
   Googlebot and Bingbot are "Search Engine Crawler". AI search crawlers (OAI-SearchBot, Exa)
   are not "AI Crawler" either, and stay allowed. Add it first, so training crawlers are never
   let in.
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
