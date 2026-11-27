import os

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlmodel import Session

from app.db import get_session
from app.routers import chores, estimation, households, invites, weeks

app = FastAPI(title="Chore Draft")

# The browser front end runs on a different address (port 5173 in development,
# a Vercel URL in production), so the API must say which sites may call it.
# CORS_ORIGINS is a comma-separated list, e.g. "https://chore-draft.vercel.app".
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(households.router)
app.include_router(invites.router)
app.include_router(chores.router)
app.include_router(estimation.router)
app.include_router(weeks.router)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Hello from Chore Draft"}


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/db")
def database_check(session: Session = Depends(get_session)) -> dict[str, str]:
    """Readiness check: can the app actually query its database?

    /health only proves the app started. This one runs a query, so a wrong
    DATABASE_URL or an unreachable database shows up as 503 here instead of
    as errors on real requests.
    """
    try:
        version = session.exec(text("SELECT version_num FROM alembic_version")).one()[0]
    except Exception:
        raise HTTPException(status_code=503, detail="Database unreachable or not migrated") from None
    return {"database": "ok", "migration": version}


@app.get("/version")
def version() -> dict[str, str]:
    return {"version": "0.1.0"}
