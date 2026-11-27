from fastapi import FastAPI

from app.routers import chores, estimation, households, invites, weeks

app = FastAPI(title="Chore Draft")

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


@app.get("/version")
def version() -> dict[str, str]:
    return {"version": "0.1.0"}
