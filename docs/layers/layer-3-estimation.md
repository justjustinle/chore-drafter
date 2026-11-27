# Layer 3: Estimation

## What it does
The owner starts estimation. Every member votes 1 to 10 on every chore, and
nobody can see anyone else's numbers. When the last vote arrives, the round
closes by itself and each chore's effort becomes the average vote, rounded
up. The owner can force-close early.

## Files
- `app/clock.py`: the single place that asks the time, so tests can fake it.
- `app/game/rules.py`: game constants (vote range, tokens, timer).
- `app/game/estimation.py`: **pure functions**: `effort_from_votes` (ceiling
  division `-(-total // count)`) and `everyone_has_voted`. No database, so
  `tests/test_estimation_logic.py` tests them directly.
- `app/identity.py`: `require_member` and `require_owner`. Every endpoint asks
  these instead of reading headers itself, so Layer 8 only changes this file.
- `app/services/estimation.py`: the database steps: start, vote, close, status.
- `app/routers/estimation.py`: four thin endpoints that call the service.
- `tests/helpers.py`: build test data through the real API.

## Things worth noticing
- **Upsert.** A vote is `INSERT ... ON CONFLICT (round_id, chore_id, member_id)
  DO UPDATE`, so voting again overwrites, and a race between two identical
  votes cannot create a duplicate.
- **Row lock on the round.** `cast_vote` locks the open round
  (`SELECT ... FOR UPDATE`). Without it, two "last" votes arriving together
  could each miss the other's vote, and neither would close the round.
- **Blindness is tested.** The status test checks that the response contains
  no vote values at all.

## Interview questions
1. Why is the rounding done with `-(-total // count)` instead of `math.ceil(total / count)`?
2. Two members cast the final two votes at the same moment. Without the row lock, what goes wrong?
3. Why keep `effort_from_votes` as a pure function instead of computing it inside the endpoint?
