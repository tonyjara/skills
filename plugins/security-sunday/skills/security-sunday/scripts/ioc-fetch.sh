#!/usr/bin/env bash
# Builds an IOC file for ioc-check.mjs from GitHub's advisory database.
#
#   scripts/ioc-fetch.sh <since YYYY-MM-DD> [GHSA-id ...] > ~/.cache/security-sunday/<date>-gh-malware.txt
#
# The output is large (~100k lines for five months), so it lives in that cache, not in git.
#
# Takes every npm malware advisory published since <since>, plus any extra advisories named
# (compromises filed as ordinary advisories, e.g. a hijacked release of a real package).
# Exact versions ("= 1.2.3") become name@1.2.3, a range with no upper bound (">= 0", "> 0",
# ">= 99.0.0" for dependency-confusion squats) becomes the bare name, any other range is
# written as a comment to check by hand.
# Needs gh logged in; read-only.
set -euo pipefail
since=${1:?usage: ioc-fetch.sh <since YYYY-MM-DD> [GHSA-id ...]}
shift

jq_lines='.vulnerabilities[] | select(.package.ecosystem == "npm") | "\(.package.name)\t\(.vulnerable_version_range)\t\($id)"'

{
  gh api --paginate "/advisories?type=malware&ecosystem=npm&per_page=100&published=>=${since}" \
    --jq ".[] | .ghsa_id as \$id | ${jq_lines}"
  for id in "$@"; do
    gh api "/advisories/${id}" --jq ".ghsa_id as \$id | ${jq_lines}"
  done
} | awk -F'\t' -v today="$(date +%F)" '
  BEGIN { print "# from GitHub advisories, generated " today }
  {
    n = split($2, parts, /,|\|\|/)
    for (i = 1; i <= n; i++) {
      r = parts[i]; gsub(/^ +| +$/, "", r)
      if (r ~ /^= /)        { sub(/^= /, "", r); print $1 "@" r }
      else if (r ~ /^>=? /)  { print $1 }   # no upper bound: every version from there on is bad
      else                  { print "# check by hand: " $1 " " r " (" $3 ")" }
    }
  }' | awk '!seen[$0]++'
