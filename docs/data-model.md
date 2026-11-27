# Data model

The tables Layer 2 builds. It follows the spec's reference model, updated
for `docs/decisions.md` (no snake draft, no minimum effort, +1 token per
nomination, owner `finish` fallback).

Conventions:
- Every table's own key is `id`. A column named `<table>_id` points to that table.
- `→` marks a foreign key. `null` means the column may be empty, and the note says when.

```text
user ──< member >── household
              │          │
              │          ├──< invite
              │          ├──< chore ──< week_chore >── week
              │          ├──< estimation_round ──< effort_vote
              │          └──< week ──< chore_flag
              │                  └──< auction_lot ──< auction_action
              └── (members vote, bid, win chores, flag chores)
```
`A ──< B` means one A has many B.

## Setup

### user
A person. One user can be a member of several households.

| column | type | notes |
|---|---|---|
| id | int | primary key |
| email | text | **unique** |
| first_name | text | |
| last_name | text | null: optional |
| created_at | datetime | |

### household
| column | type | notes |
|---|---|---|
| id | int | primary key |
| name | text | |
| phase | SETUP / ESTIMATION / ACTIVE | |
| owner_member_id | int → member.id | the owner is a *member*: ownership belongs to one household |
| created_at | datetime | |

### member
A user's seat in one household.

| column | type | notes |
|---|---|---|
| id | int | primary key |
| household_id | int → household.id | |
| user_id | int → user.id | |
| display_name | text | the name shown in this household |
| turn_order | int | 1, 2, 3… in join order; used for nomination order and tie-breaks |
| joined_at | datetime | |

**unique (household_id, user_id)**: a user joins a household at most once.

### invite
| column | type | notes |
|---|---|---|
| id | int | primary key |
| household_id | int → household.id | |
| email | text | who it is for |
| token | text | **unique**; from `secrets.token_urlsafe` |
| invited_by | int → member.id | |
| expires_at | datetime | |
| accepted_at | datetime | null until used |

No status column: "used" means `accepted_at` is not null, and "expired" means
`expires_at` is in the past. Both are worked out from the data, so they can never
drift out of date.

### chore
| column | type | notes |
|---|---|---|
| id | int | primary key |
| household_id | int → household.id | |
| name | text | |
| description | text | null: optional |
| effort_points | int | null until the first estimation closes; the *current* value |
| created_by | int → member.id | |

## Estimation

### estimation_round
One round of blind voting: the first estimation, or a re-estimation in a week.

| column | type | notes |
|---|---|---|
| id | int | primary key |
| household_id | int → household.id | |
| week_id | int → week.id | null for the first estimation |
| opened_at | datetime | |
| closed_at | datetime | null while voting is open |
| force_closed | bool | true if the owner closed it early |

Rule: at most one open round per household at a time (`closed_at` is null).

### effort_vote
| column | type | notes |
|---|---|---|
| id | int | primary key |
| round_id | int → estimation_round.id | |
| chore_id | int → chore.id | |
| member_id | int → member.id | |
| points | int | 1 to 10 |

**unique (round_id, chore_id, member_id)**: one vote per person, per chore, per
round. Voting again overwrites the earlier vote.

## Weeks

### week
| column | type | notes |
|---|---|---|
| id | int | primary key |
| household_id | int → household.id | |
| starts_on | date | |
| opened_at | datetime | when the week opened; members who joined later play from next week |
| status | OPEN / AUCTION / ASSIGNED / CLOSED | OPEN is for flagging and re-estimation before the auction |
| nomination_member_id | int → member.id | null outside the auction; whose turn it is to nominate |
| nomination_turn | int | increases every nomination turn; used to reject stale requests |
| nomination_deadline | datetime | null outside the auction; 30-second timer |

**unique (household_id, starts_on)**: one week per start date.

Tokens are **not stored**. A member's budget = 100 + the number of `auction_lot`
rows in the week − the sum of `price_paid` on the chores they won.

### chore_flag
A member asking for a chore to be re-estimated this week.

| column | type | notes |
|---|---|---|
| id | int | primary key |
| week_id | int → week.id | |
| chore_id | int → chore.id | |
| member_id | int → member.id | |

**unique (week_id, chore_id, member_id)**: one flag per person, per chore, per week.

### week_chore
One chore in one week. This is both the **results** and the **history**: there is
no separate history table, because history is just the `week_chore` rows of
closed weeks.

| column | type | notes |
|---|---|---|
| id | int | primary key |
| week_id | int → week.id | |
| chore_id | int → chore.id | |
| effort_points | int | **snapshot**, copied from `chore` when the week opens |
| assigned_member_id | int → member.id | null until sold or assigned |
| assigned_via | AUCTION / FINISH | null until assigned |
| price_paid | int | null unless won at auction |
| done_at | datetime | null until marked done |

**unique (week_id, chore_id)**: each chore appears once per week.

The snapshot is why week 3 still shows 5 after re-estimation changes the chore
to 8 in week 5.

## Auction

### auction_lot
One chore going under the hammer.

| column | type | notes |
|---|---|---|
| id | int | primary key |
| week_id | int → week.id | |
| week_chore_id | int → week_chore.id | **unique**: a chore is auctioned at most once per week |
| nominated_by | int → member.id | |
| status | OPEN / SOLD | |
| high_bid | int | starts at the opening bid |
| high_bidder_id | int → member.id | starts as the nominator |
| turn_member_id | int → member.id | null once sold; whose turn to bid or pass |
| turn_number | int | increases on every action; requests must send the current one |
| turn_deadline | datetime | null once sold |

Rule: at most one OPEN lot per week.
The request handler locks this row (`SELECT ... FOR UPDATE`) while handling a bid.

### auction_action
Every bid and pass. This is the auction's audit trail.

| column | type | notes |
|---|---|---|
| id | int | primary key |
| lot_id | int → auction_lot.id | |
| member_id | int → member.id | |
| kind | BID / PASS | |
| amount | int | null for a pass |
| turn_number | int | the turn this action was for |
| timed_out | bool | true if the server recorded a pass because the deadline passed |
| created_at | datetime | |

**unique (lot_id, turn_number)**: only one action can ever be recorded for a turn,
even if two requests race. This is the last line of defence.

## Reliability

### idempotency_record
The saved response for an auction request sent with an `Idempotency-Key`
header (Layer 6, migration 0003). It replaced the spec's
`auction_action.idempotency_key` column, because nominations create a lot as
well as an action, and a retry must get back the whole original response.

| column | type | notes |
|---|---|---|
| id | int | primary key |
| member_id | int → member.id | keys belong to one member |
| key | text | the client's random key |
| path | text | the endpoint it was used on; reusing a key elsewhere is 422 |
| status_code | int | |
| response_body | json | the response sent the first time |
| created_at | datetime | |

**unique (member_id, key)**

