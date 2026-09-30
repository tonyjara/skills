---
name: best-coding-practices
description: Habits for writing and changing code in an existing codebase — read before editing, match the surrounding style, keep the diff to what was asked, check inputs at the boundary, and verify before saying it works. Use when implementing a feature, fixing a bug, refactoring, or reviewing a change, and whenever the user asks for "best practices", "clean code", or "do this properly".
---

# Best coding practices

These are habits, not rules to recite. Apply them quietly; mention one only when
it changes what you are about to do.

## Before writing anything

- **Read the code you are about to change, and the code that calls it.** A fix
  written from the function alone breaks the caller that relied on the bug.
- **Find the project's own instructions first** — `CLAUDE.md`, `AGENTS.md`,
  `CONTRIBUTING.md`, a `docs/` folder. They override everything below.
- **Look for the thing that already exists.** Search for a helper before writing
  one. Two functions that do the same job drift apart and both end up wrong.
- **If the request is ambiguous in a way that changes the design, ask.** If it is
  ambiguous only in a detail with an obvious default, pick the default and say so.

## While writing

- **Match the surrounding code** — naming, error handling, comment density,
  file layout. A consistent codebase in a style you dislike beats an
  inconsistent one in a style you like.
- **Keep the diff to what was asked.** No drive-by renames, reformatting, or
  "while I was here" refactors. Note them for the user instead; a reviewer can
  approve a small diff and cannot approve a sprawling one.
- **Check inputs where they cross a boundary** (network, file, user, another
  process), and trust them after that. Refuse bad input rather than quietly
  fixing it: a clamp hides the bug that sent the value, and `NaN` passes
  through most clamps untouched.
- **Name things for what they mean, not how they are built.** `retryDeadline`,
  not `ts2`.
- **Comments explain why** — the decision, the constraint, the alternative that
  was rejected. Never a comment that restates the next line.
- **Handle the failure path on purpose.** Every `catch` either recovers, adds
  context and rethrows, or reports. An empty `catch` is a bug report nobody
  will receive.
- **Prefer plain code to clever code.** Reach for an abstraction the third time
  you need it, not the first.

## Before saying it is done

- **Run it.** The type checker, the tests, and — for anything a person sees —
  the thing itself. "It should work" is not a result.
- **Test the pure parts.** Logic you can pull out of I/O is logic you can test
  cheaply; do that rather than mocking the world.
- **Report honestly.** If a test fails, show the output. If you skipped a step,
  say which one. If you are unsure, say what would settle it.
- For a change worth a second look, walk
  [the review checklist](references/review-checklist.md).

## Things that are never "best practice" to do unasked

- Deleting or overwriting files you have not looked at.
- Committing, pushing, or rewriting git history.
- Disabling a test, a lint rule, or a type check to make something pass.
- Adding a dependency for something a few lines would do.
