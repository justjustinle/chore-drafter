# Reliability: retries, idempotency, webhooks and scheduled jobs

## Why requests get repeated
Networks fail in the worst place: **after** the server has done the work but
**before** the reply reaches the phone. The app sees an error or a timeout,
cannot tell whether the bid happened, and retries. People double-tap too.
So the server must assume any request can arrive twice.

## Idempotent means "doing it twice is the same as doing it once"
- **Naturally idempotent:** `PUT .../votes/{chore_id}` (an upsert: the second
  vote overwrites the first), `finish` (only assigns chores with no member,
  returns early if already ASSIGNED), `close`, `done`.
- **Made idempotent with a key:** `nominate`, `bid`, `pass`. These change state
  and cannot simply be repeated, so the client sends `Idempotency-Key: <random>`
  and resends the *same* key when retrying. The server stores the first
  response under that key and replays it.
- **turn_number is not enough on its own.** It stops a retry from acting twice,
  but the retry gets a 409 "turn moved on" even though the bid succeeded. The
  key turns that into the original 200.

The record is saved in the same transaction as the action. If they were saved
separately, a crash between the two would leave an action with no record,
and the retry would act a second time.

## Retries with backoff
A client that retries should wait a little longer each time (for example 1s,
2s, 4s, plus a random "jitter") so that a struggling server is not hit by
every client at the same instant. Only retry requests that are idempotent
or carry a key.

## Webhooks
A webhook is the reverse direction: another service (an email provider, a
payment provider) calls *your* endpoint when something happens. Providers
retry when you do not answer quickly with a 2xx, so the same event often
arrives more than once. Treat webhooks like any other repeated request:
store each event's id and ignore ids you have already processed. Also
verify the provider's signature so nobody else can fake events.

## Scheduled jobs
A job that runs on a timer (Layer 7) has the same problem: it may run twice
(a retry after a crash, two servers both running it, a person running it by
hand). The answer is the same: make every step idempotent. The weekly job
reuses `finish`, `close_week` and `open_week`, which already are, and checks
"is there already a week starting on this date?" before opening one.
