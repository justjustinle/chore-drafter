# Layer 6: Reliability

## What it does
Makes it safe for clients to retry. Finishing and closing a week were already
idempotent (Layer 5). This layer adds `Idempotency-Key` to nominate, bid and
pass, and writes up retries, webhooks and scheduled jobs in `docs/reliability.md`.

## Files
- `app/idempotency.py`: `replay` (return the saved response for a known key)
  and `save` (store the response with the action).
- `app/models.py`: the new `IdempotencyRecord` table; migration
  `0003_idempotency_records.py` creates it and drops the unused
  `auction_action.idempotency_key` column.
- `app/services/auction.py`: nominate, bid and pass no longer commit
  themselves. The router commits once, after saving the record.
- `app/routers/weeks.py`: the three auction actions accept the header.
- `tests/test_idempotency.py`: repeated key, retry after the auction moved on,
  key reused on another endpoint, keys per member, nominate retried, and two
  identical retries at the same moment.

## Interview questions
1. A bid succeeds but the reply is lost. Without an idempotency key, what does the retry get back, and why is that a problem?
2. Why must the idempotency record be committed in the same transaction as the bid?
3. A payment provider sends the same webhook three times. How do you make sure you only act once?
