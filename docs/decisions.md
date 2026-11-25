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

## Still open

- Force-closed estimation with a chore nobody voted on (Layer 3).
- Placeholder values: vote range 1–10, 30-second turn timer, 7-day invite
  expiry.
- Whether the first nominator rotates each week (Layer 4).
- Whether one flag is enough to re-estimate a chore, or a majority (Layer 4).
- What a member who joins mid-week gets (tokens, turn order) (Layers 1 and 4).
