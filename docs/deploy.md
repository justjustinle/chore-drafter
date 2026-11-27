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

2. **Create the database.** In the project, open the **Storage** tab →
   **Create Database** → **Neon (Serverless Postgres)** → follow the steps,
   and connect it to this project for all environments. Vercel then adds
   environment variables to the project, including:
   - `DATABASE_URL`: the *pooled* connection (its host contains `-pooler`).
     The app uses this.
   - `DATABASE_URL_UNPOOLED`: a *direct* connection. Use this one for migrations.

   `app/db.py` turns Neon's `postgres://...` URLs into the form SQLAlchemy
   needs, and on Vercel opens one connection per request (no pool), which is
   what a pooled serverless database expects.

3. **Create the tables (run once, from your PC).** Copy the value of
   `DATABASE_URL_UNPOOLED` from *Settings → Environment Variables*. Then, in
   the project folder with your venv active:

   PowerShell:
   ```powershell
   $env:DATABASE_URL = "paste-the-unpooled-url-here"
   ```
   ```powershell
   alembic upgrade head
   ```
   ```powershell
   Remove-Item Env:DATABASE_URL
   ```

   cmd:
   ```bat
   set DATABASE_URL=paste-the-unpooled-url-here
   ```
   ```bat
   alembic upgrade head
   ```
   ```bat
   set DATABASE_URL=
   ```

   The last line points your terminal back at your local Docker database.
   Run `alembic upgrade head` like this again whenever a new migration is merged.

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
