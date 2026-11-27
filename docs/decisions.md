# Decisions

Changes to, and clarifications of, the Chore Draft spec. Where this file
and the spec disagree, this file wins. Each entry says when it was decided
and which layers it affects.

## Identity until auth (Layer 1, affects Layer 8)

- Until auth exists, the caller identifies themselves with headers:
  `X-User-Email` and `X-User-Name` on `POST /households`, `X-User-Name` on
  `POST /invites/{token}/accept` (the email comes from the invite), and
  `X-User-Email` on `POST /households/{id}/chores`.
- Layer 8 replaces these headers with a per-member API key.
- Adding a chore as someone who is not a member returns **403**.

## Request validation (Layer 1)

- Create models use `extra="forbid"`: a field the model does not declare
  is rejected with **422** instead of being silently ignored.

## Users and members (Layer 2)

- `user` and `member` are separate tables. A user is a person (unique
  email); a member is that person's seat in one household, with
  `unique (household_id, user_id)`.

## Auction and draft (Layer 2, affects Layers 4, 5 and 7)

Replaces the spec's decline rule, snake draft and minimum effort.

1. **No declining.** A member must nominate on their nomination turn.
   `POST /weeks/{id}/auction/decline` is removed.
2. **Auction end.** The auction ends when every chore is sold, or when the
   owner finishes the week early (rule 5).
3. **+1 token per nomination.** When a chore is nominated, every member
   immediately gets +1 token, credited before the opening bid is checked.
   So a nominator always has at least 1 token.
   Budget = 100 + chores nominated so far this week − tokens spent.
   This is calculated, not stored.
4. **Timeouts.** A timeout on a nomination turn skips that turn; the member
   nominates again when the rotation comes back round. A timeout on a
   bidding turn is a pass for that chore only.
5. **Finish fallback.** The owner calls `POST /weeks/{id}/finish` to assign
   any unsold chores: sort them from highest to lowest effort, and give each
   one to the member with the lowest effort total so far this week. Ties go
   to the earlier joiner. The Layer 7 scheduled job can call the same
   function. Layer 5 builds this as a pure function.
6. **No minimum effort, no snake draft.** `week.minimum_effort` is dropped.

## Data model additions (Layer 2)

See `docs/data-model.md`. Compared with the spec's reference model:
- `week.status` gains **OPEN**, before AUCTION, for flagging and
  re-estimation. DRAFTED is renamed **ASSIGNED**, because there is no draft.
- `week` holds the nomination turn: `nomination_member_id`,
  `nomination_turn` and `nomination_deadline`.
- New **`chore_flag`** table for re-estimation flags.
- `week_chore.assigned_via` is AUCTION or FINISH.
- `auction_action.timed_out` marks passes the server recorded automatically.
- `week.minimum_effort` is removed.

## Defaults for the open questions (agreed before Layer 3)

1. **Force-close with an unvoted chore:** blocked with **409**, and the
   message names the chores that have no votes.
2. **Nomination order across weeks:** the first nominator rotates each week.
3. **Re-estimation trigger:** one flag is enough to re-estimate a chore.
4. **Joining mid-week:** a member who joins during a week takes part from the
   next week. They do not vote in rounds that opened before they joined, and
   they are not in an auction that started before they joined.
5. **Placeholder values stay:** votes 1 to 10, a 30-second turn timer, and
   7-day invites (see `app/game/rules.py`).

## Estimation details (Layer 3)

- The voters in a round are the members whose `joined_at` is not after the
  round's `opened_at`.
- Votes are allowed whenever the household has an open round (the first
  estimation, or a re-estimation during a week), not only in phase ESTIMATION.
- Owner-only actions (start, force-close) return **403** for anyone else.
  The caller is identified by `X-User-Email` until Layer 8.

## Weeks and auction details (Layer 4)

- **Extra endpoints** the spec needed but did not list:
  - `GET /weeks/{id}`: the week and its chores.
  - `POST /weeks/{id}/estimation/start` (owner): opens the re-estimation round
    for flagged chores. Votes use the normal estimation vote endpoint.
  - `POST /weeks/{id}/auction/start` (owner): moves the week from OPEN to
    AUCTION. Blocked while flagged chores have not been re-estimated.
- `week.opened_at` (migration 0002) records when a week opened. The members
  playing a week are those who had joined by then.
- **The row lock is on the week**, not the lot. Nominations happen between
  lots, so the week is the one row every auction action shares.
- **Order of checks:** a stale `turn_number` is **409** whoever sent it; only
  then is the wrong member **403**. A late or repeated click always reads as
  "that turn has moved on".
- Spending more tokens than you have is **409**.
- The nominator's opening bid is stored as a BID action with turn number 0.
- `GET /weeks/{id}/auction` also works once the week is ASSIGNED, so polling
  clients see the auction end.

## Finish, results and history (Layer 5)

- `POST /weeks/{id}/finish` (owner) replaces the spec's `POST /weeks/{id}/draft`.
  It works from OPEN or AUCTION. A chore that is mid-auction goes to its
  current high bidder at their bid; every other unsold chore is assigned by
  `app/game/finish.py`.
- `POST /weeks/{id}/close` (owner) is new: ASSIGNED → CLOSED. Closing twice
  is harmless.
- Marking a chore done twice keeps the first time.
- History shows each week's snapshot effort, not the chore's current value.

## Reliability (Layer 6)

- `Idempotency-Key` (optional header, up to 100 characters) on nominate, bid
  and pass. Keys are per member. A repeated key returns the saved response
  with no new action; the same key on a different endpoint is **422**.
- Only successful responses are saved. A failed request changed nothing, so
  retrying it simply runs it again.
- The action, its response and the idempotency record are committed in one
  transaction, while the week row is locked.
- `auction_action.idempotency_key` is replaced by the `idempotency_record`
  table (migration 0003).

## Auth (Layer 8)

- **One API key per member**, created when they create a household or accept an
  invite, and returned **once** in that response (`api_key`). Only its
  SHA-256 hash is stored (`member.api_key_hash`, migration 0004).
- Every endpoint except creating a household and accepting an invite needs
  `X-API-Key`. A missing or unknown key is **401**; a valid key used on
  another household is **403**.
- The `X-User-Email` / `X-User-Name` headers now only identify a *new* person:
  on `POST /households` (both) and `POST /invites/{token}/accept` (name).
- A key belongs to one membership. The same person in two households has two
  keys, and each works only in its own household.
- **Owner-only:** invites, start and force-close estimation, start
  re-estimation, start the auction, finish and close a week. Invites now
  record `invited_by`.
- Reading a household or its chores now needs membership (the spec said "any").
