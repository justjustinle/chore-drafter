"""Idempotency keys: make retries safe.

A phone on a bad connection sends "bid 10", the reply gets lost, and the app
retries. Without protection the retry is a second request: at best it is
rejected (the turn moved on) and the user sees a confusing error; at worst it
acts twice. With an Idempotency-Key header, the client sends the same random
key on every retry, and the server answers a repeated key with the response
it saved the first time, without acting again.
"""

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from app.models import IdempotencyRecord, Member


def replay(session: Session, member: Member, key: str | None, path: str) -> JSONResponse | None:
    """The saved response for this key, or None if the key is new (or absent)."""
    if key is None:
        return None
    record = session.exec(
        select(IdempotencyRecord).where(IdempotencyRecord.member_id == member.id, IdempotencyRecord.key == key)
    ).first()
    if record is None:
        return None
    if record.path != path:
        raise HTTPException(status_code=422, detail="This Idempotency-Key was used for a different request")
    return JSONResponse(content=record.response_body, status_code=record.status_code)


def save(session: Session, member: Member, key: str | None, path: str, response: BaseModel) -> None:
    """Store the response in the same transaction as the action it describes."""
    if key is None:
        return
    session.add(
        IdempotencyRecord(
            member_id=member.id,
            key=key,
            path=path,
            status_code=200,
            response_body=response.model_dump(mode="json"),
        )
    )
