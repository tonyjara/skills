# Review checklist

Walk this before handing a change back. Each line is a question; a "no" is
either fixed or said out loud.

## Correctness

- Does it do what was asked, and only that?
- What happens with empty input, one item, a very large input, and a malformed one?
- Is every value from outside the process checked before it is used?
- Are errors handled, or at least surfaced with enough context to act on?
- Is anything shared between concurrent callers, and is that safe?

## Fit

- Does it read like the code around it?
- Did it reuse what the codebase already has instead of adding a second version?
- Is every new dependency worth what it costs?
- Would the next person understand *why* from the code and its comments?

## Evidence

- Did the type checker and the tests actually run, and pass?
- Is there a test for the logic that changed, where the logic is testable?
- For a visible change: was it seen working, not just compiled?

## Hand-off

- Is the summary honest about what was verified and what was not?
- Are the follow-ups you noticed but did not do listed for the user?
