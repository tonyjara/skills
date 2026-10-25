# Report template

## Per project (a project agent's final message)

```markdown
### <project> — <YYYY-MM-DD>

**Result:** done / done with items left / blocked
**Commit:** <sha> on <branch> (pushed / PR #n / not pushed: why)
**Deploy:** <url> healthy at HH:MM / failed: … / no deploy (why)

Audit: before C/H/M <n/n/n> → after <n/n/n>. IOC check: clean / HIT (stop).

Fixed:
- <pkg> a → b (CVE-…, severity)
- <n> other patch/minor updates
- Node a → b in <files>

Not fixed, and why:
- <pkg> (CVE-…): fix only in <major>, needs <work>

Majors left:
- <pkg> a → b: <what it would take>

Needs the user:
- <decision or manual step>

Inventory changes:
- <key>: <old> → <new>

Skill changes:
- <what was wrong or missing in the skill>
```

## Sunday summary (the coordinator, after every report is in)

Save it as `briefs/<YYYY-MM-DD>-report.md` and post the short version to the user.

```markdown
# Security Sunday <YYYY-MM-DD>

**Urgent from the brief:** <one line each>

| Where | Result | Fixed | Left | Needs you |
|---|---|---|---|---|
| Mac | | | | |
| nytojara-vps | | | | |
| <project> | | | | |

## Fixed
## Not fixed, and why
## Needs the user
## Skill changes made
```
