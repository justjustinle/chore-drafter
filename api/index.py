"""Vercel entry point: serves the FastAPI backend under /api.

Vercel runs Python files in the api/ folder as serverless functions. This
one wraps the real app (app/main.py) and mounts it at /api, so the same
Vercel project can serve the front end at / and the API at /api/... on one
address. That means no cross-origin (CORS) setup is needed in production.

Locally nothing changes: `fastapi dev app/main.py` still serves the API at /.
"""

from fastapi import FastAPI

from app.main import app as chore_draft

app = FastAPI(title="Chore Draft on Vercel", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/api", chore_draft)
