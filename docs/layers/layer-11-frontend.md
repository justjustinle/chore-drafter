# Layer 11: The browser front end

A React + TypeScript app (built with Vite) in `frontend/`, styled as a cosy
2D RPG market and quest board. The backend owns every rule; the front end
only shows what the API returns and sends actions.

## Run it
In one terminal, the API (from the project root):
```bash
fastapi dev app/main.py
```
In another, the front end:
```bash
cd frontend
```
```bash
npm install
```
```bash
npm run dev
```
Open http://localhost:5173. To see every screen without the backend, open
http://localhost:5173/demo (pretend data, nothing is saved).

## How it is organised
- `src/api/client.ts`: **the only file that talks to the backend.** Every
  endpoint is one function on the `Api` interface. Auction actions send
  `turn_number` and an `Idempotency-Key`, and a retry after a network error
  reuses the same key.
- `src/api/live.ts`: **the only place that polls.** Screens call `useLive()`;
  switching to WebSockets in Layer 12 changes this file, not the screens.
- `src/api/session.ts`: the API keys this browser holds, in localStorage.
- `src/api/types.ts`: the response shapes, mirroring `app/schemas.py`.
- `src/mock/mockApi.ts`: the same `Api` interface returning fixed JSON, used
  by `/demo`. The demo auction ticks along on its own.
- `src/pages/HouseholdPage.tsx`: picks the screen from the household phase and
  week status the API returns. No local flags decide which screen shows.
- `src/screens/`: Setup, Estimation (with the flip reveal), OpenWeek, Auction,
  QuestWeek, History, BetweenWeeks.
- `src/screens/auctionEvents.ts`: the Town Crier. There is no events endpoint,
  so it compares each poll with the previous one.

## Where the brief and the agreed rules differ
The brief predates some decisions in `docs/decisions.md`, so the screens
follow the current rules:
- **No weekly minimum.** The workload bar shows each member's share of the
  week's total effort instead.
- **No "decline to nominate".** Nominating is compulsory.
- **No unsold pile or draft.** Every chore is sold, or handed out by the
  owner's **"The Guild Assigns"** button (`POST /weeks/{id}/finish`). Assigned
  chores are dealt onto the quest board one at a time.
- **Tokens:** "100 tokens each, +1 for everyone per nomination".
- **"Draft Magnet" title** is "Guild's Pick" (most chores assigned by the guild).

## Backend additions for the front end
- `GET /me`: who an API key belongs to (used after pasting a key).
- Households include `current_week` and `estimation_open`.
- Weeks include `flagged_chore_ids`; week chores include `description`.
- The auction state includes `passed_member_ids`, `sold_chores` and
  `server_time` (so the timer drains towards the server's deadline even if the
  device clock is off).
- CORS, configured with `CORS_ORIGINS` (default `http://localhost:5173`).

## Accessibility
- Keyboard on your bidding turn: Space or 1 = +1, 2 = +5, 3 = +10,
  A = All-In, P = Pass.
- `prefers-reduced-motion`: no popups, confetti, bounces or slides.
- State is never shown by colour alone: chips have icons and words, the timer
  has a text countdown, done/not done has a tick and a label.

## Deploying
See `docs/deploy.md`: one Vercel project serves the front end at `/` and the
API at `/api`, with Neon for Postgres.

## Interview questions
1. Why does the timer use the server's deadline and `server_time` instead of counting down 30 seconds locally?
2. There is no events endpoint. How does the ticker know "Sam passed", and what could it miss?
3. Why put every fetch behind one `Api` interface, with a mock implementation alongside the real one?
