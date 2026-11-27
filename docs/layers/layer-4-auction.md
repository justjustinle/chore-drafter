# Layer 4: Weeks and the live auction

## What it does
A week opens and copies each chore's effort into the week. Members can flag
chores for re-estimation. Then the owner starts the auction: members take
turns nominating a chore with an opening bid (everyone gets +1 token when
they do), bidding goes round the table, and the chore sells when everyone
else has passed. A turn that runs past 30 seconds counts as a pass (or, for
a nomination, as a skipped turn).

## Files
- `app/game/auction.py`: **pure functions**: tokens left, next in rotation,
  next bidder, skipping timed-out nominations, first nominator of the week.
- `app/services/weeks.py`: open a week (with the snapshot), flags,
  re-estimation, start the auction.
- `app/services/auction.py`: nominate, bid, pass, sell, and the lazy timer.
- `app/routers/weeks.py`: the HTTP endpoints, each one a few lines long.
- `migrations/versions/0002_week_opened_at.py`: adds `week.opened_at`, filling
  in existing rows with a temporary default.

## The three layers of protection
1. **turn_number:** every action says which turn it is for. If the turn has
   moved on, the request is rejected with 409. This catches double-taps,
   retries and late clicks.
2. **Row lock:** every auction request locks the week row first
   (`SELECT ... FOR UPDATE`), so two requests for the same week run one after
   the other.
3. **Unique (lot_id, turn_number):** even if the code were wrong, the
   database will not store two actions for one turn.

`test_two_bids_for_the_same_turn_at_once_exactly_one_wins` fires two bids
from two threads at the same instant. With the lock removed, the test either
passes by luck or hits the unique constraint, which is why all three layers
exist.

## The lazy timer
No background job counts down the seconds. Every auction request, including
the polling `GET`, first checks the deadline and records any passes that
should already have happened. Each catch-up turn starts at the previous
deadline, not "now", so nobody loses time. Missed nomination turns are
worked out with division, so a server left idle for a day does not loop
thousands of times.

## Interview questions
1. Why lock the week row instead of the lot row?
2. Why does the timer catch up from the old deadline rather than from the current time?
3. "Tokens left" is never stored. What would go wrong if it were a column that each bid updated?
