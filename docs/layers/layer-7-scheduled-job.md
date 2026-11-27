# Layer 7: The scheduled job

## What it does
`scripts/weekly.py` is a plain Python script with two commands:

```bash
python -m scripts.weekly open-week
```
Sunday: for every ACTIVE household, finish and close last week if needed,
open this week, and send the reminder (a log line until email exists).

```bash
python -m scripts.weekly finish-unfinished
```
Monday: if an earlier week's ceremony never finished, assign its chores
with the same `finish` the owner can call.

`--date 2026-11-29` pretends today is that date, which is handy for testing
by hand.

## How it runs on a schedule
Something outside the app runs it on a timer:
- **On a Linux server:** cron, e.g. `0 18 * * 0` (Sundays 18:00) for
  `open-week` and `0 6 * * 1` (Mondays 06:00) for `finish-unfinished`.
- **On Azure (Layer 10):** an Azure Container Apps *job* with a cron schedule,
  using the same container image as the API.

## Why it is safe to run twice
Every step checks the state first: a week that already starts today is not
opened again, `finish` does nothing to an ASSIGNED week, and `close_week`
does nothing to a CLOSED one. The tests run each command twice and check
that nothing changes the second time.

## Why it reuses the services
The script calls `weeks.open_week`, `results.finish` and `results.close_week`,
the same functions the API calls. If a rule changes, it changes for both.
This is why Layers 3 to 6 kept the logic in `app/services/` rather than
inside the endpoints.

## Interview questions
1. Why does the script call the service functions instead of calling the HTTP API?
2. The job runs twice by mistake on Sunday. Walk through why nothing is opened twice.
3. Why does `finish-unfinished` skip a week whose `starts_on` is today?
