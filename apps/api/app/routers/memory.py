from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from packages.db.database import SessionLocal
from packages.memory.service import MemoryRetriever, ingest_messages

router = APIRouter()


@router.post("/memory/ingest/messages")
def ingest_messages_endpoint(since_hours: int = 24, chat_id: str | None = None) -> dict[str, Any]:
    with SessionLocal() as session:
        created = ingest_messages(session, since_hours=since_hours, chat_id=chat_id)
    return {"status": "ok", "created": created}


@router.get("/memory/search")
def memory_search(
    q: str = Query(..., min_length=1),
    tag: list[str] | None = Query(default=None),
    limit: int = Query(default=8, ge=1, le=50),
    chat_id: str | None = None,
) -> dict[str, Any]:
    with SessionLocal() as session:
        retriever = MemoryRetriever(session)
        chunks = retriever.retrieve(q, tags=tag or [], chat_id=chat_id, limit=limit)

    payload = [
        {
            "id": chunk.id,
            "source_type": chunk.source_type,
            "source_ref": chunk.source_ref,
            "chat_id": chunk.chat_id,
            "title": chunk.title,
            "content": chunk.content,
            "tags": chunk.tags,
            "topic": chunk.topic,
            "created_at": chunk.created_at.isoformat(),
        }
        for chunk in chunks
    ]
    return {"status": "ok", "items": payload}
