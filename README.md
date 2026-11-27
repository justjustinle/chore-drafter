# Chore Draft

A household chore app run as a live auction. Housemates vote on how big each
chore is, bid tokens on the chores they want, and anything left unsold is
shared out so the effort evens out.

Built in layers with FastAPI, SQLModel, Postgres and Alembic.
`docs/decisions.md` records every rule decision, `docs/data-model.md` the
tables, and `docs/layers/` explains each layer with interview questions.

## Run it locally (Windows, cmd or PowerShell)

1. Start Postgres in Docker:
   ```bash
   docker compose up -d
   ```
2. Install the libraries (inside your virtual environment):
   ```bash
   pip install -r requirements.txt
   ```
3. Create or update the tables:
   ```bash
   alembic upgrade head
   ```
4. Run the tests:
   ```bash
   pytest -q
   ```
5. Run the API and open http://127.0.0.1:8000/docs:
   ```bash
   fastapi dev app/main.py
   ```

## Using the API in /docs
1. `POST /households` with the `x-user-email` and `x-user-name` headers. The
   response includes your `api_key`. It is shown only once, so copy it.
2. Paste the key into the `x-api-key` header on every other request.
3. Invite people with `POST /households/{id}/invites`; they accept with
   `POST /invites/{token}/accept` and get their own key.

## The weekly job
```bash
python -m scripts.weekly open-week
```
```bash
python -m scripts.weekly finish-unfinished
```
See `docs/layers/layer-7-scheduled-job.md`.
