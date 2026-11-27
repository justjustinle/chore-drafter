# Deploying to Vercel (one project)

One Vercel project serves everything from one address:
- `/` and every other path: the front end (built from `frontend/`)
- `/api/...`: the FastAPI backend (`api/index.py` mounts `app/main.py` at `/api`)

Because both live on the same address, the browser needs no CORS setup and
the front end needs no `VITE_API_URL`: a production build calls `/api`.

The database is hosted Postgres from **Neon**, connected through Vercel.

## One-time setup

1. **Project settings.** In your Vercel project (`chorequest`), check
   *Settings → Build and Deployment*: **Root Directory** is the repo root (empty).
   `vercel.json` sets the install command, build command and output folder,
   so leave the framework preset as it is.

2. **The database.** It already exists: Neon project `gentle-flower-56760106`,
   branch `production` (set up with `neon init` and `neon deploy`; `neon.ts` is
   its config). Copy its two connection strings from the Neon console
   (**Connect** button), or run `neon env pull` on your PC to get them in
   `.env.local`:
   - `DATABASE_URL`: the *pooled* connection (host contains `-pooler`). The app uses this.
   - `DATABASE_URL_UNPOOLED`: the *direct* connection. Migrations use this.

   In Vercel, open **Settings → Environment Variables** and add both, for
   Production, Preview and Development.

   `app/db.py` turns Neon's `postgresql://...` URLs into the form SQLAlchemy
   needs, and on Vercel opens one connection per request (no pool) with
   prepared statements off, which is what Neon's pooled connection expects.

3. **Create the tables (run once, from your PC).** Neon's CLI writes the
   connection strings into `.env.local`, which the app and Alembic read
   automatically (Alembic uses the direct one):
   ```bash
   npm i -g neon@latest
   ```
   ```bash
   neon login
   ```
   ```bash
   neon env pull
   ```
   ```bash
   alembic upgrade head
   ```
   Run `alembic upgrade head` again whenever a new migration is merged.

   While `.env.local` exists, `fastapi dev` on your PC also uses Neon. Rename
   or delete it to go back to the local Docker database. The tests always use
   the local test database, whatever `.env.local` says.

4. **Redeploy** (*Deployments → ⋯ → Redeploy*), or push to `main`.

## Check it works
- `https://<your-app>.vercel.app/api/health` shows `{"status":"ok"}`.
- `https://<your-app>.vercel.app/` shows the guild front door. Found a guild,
  open the invite link in a private window, and play.
- `https://<your-app>.vercel.app/demo` shows every screen with pretend data.

## Not covered yet
- **The weekly job** (`scripts/weekly.py`) does not run on Vercel. Vercel Cron
  can only call a URL, so it needs two small endpoints protected by a secret.
  Until then, the owner opens weeks and uses "The Guild Assigns" by hand.
- `/api/docs` is switched off in production. Use `fastapi dev` locally for `/docs`.
