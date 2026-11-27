# Layer 5: The finish fallback and results

## What it does
If the auction cannot finish, the owner calls `finish`: every unsold chore
is assigned so that effort evens out. Then members mark their chores done,
the owner closes the week, and it appears in the history.

## Files
- `app/game/finish.py`: `assign_leftovers`, a **pure function**. Biggest chore
  first, each to whoever has the lowest effort total so far; ties go to the
  earliest joiner. This is the "greedy" way to balance a workload.
- `tests/test_finish_logic.py`: the spec's edge cases, without a database:
  nobody bids, one member hoards, a tie, a single member, nothing left,
  totals that cannot balance, and input order not mattering.
- `app/services/results.py`: finish, assignments, mark done, close, history.
- New endpoints in `app/routers/weeks.py`: finish, assignments, done, close, history.

## Things worth noticing
- **The pure function does not know about the database.** The service loads
  the data, calls `assign_leftovers`, and writes the answer back. Layer 7's
  scheduled job reuses exactly the same service.
- **Idempotent by design.** `finish` only touches chores with no member yet and
  returns early if the week is already ASSIGNED, so running it twice changes
  nothing. `close` and `done` behave the same way.
- **Snapshots pay off.** The history test re-estimates a chore after its week
  closed and checks that the history still shows the old value.

## Interview questions
1. Why sort the leftovers biggest first before handing them out?
2. What makes `finish` safe to call twice, and why does that matter for a scheduled job?
3. Why pass `effort_so_far` into the pure function instead of letting it read the database?
