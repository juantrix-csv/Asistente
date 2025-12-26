from __future__ import annotations

from fastapi import APIRouter, Query

from packages.db.database import SessionLocal
from packages.db.models import AssistantRequest

router = APIRouter()


@router.get("/requests")
def list_requests(status: str | None = Query(default=None), limit: int = Query(default=50)) -> list[dict]:
    with SessionLocal() as session:
        query = session.query(AssistantRequest)
        if status:
            query = query.filter(AssistantRequest.status == status)
        rows = (
            query.order_by(AssistantRequest.created_at.desc())
            .limit(limit)
            .all()
        )

    return [
        {
            "id": row.id,
            "request_type": row.request_type,
            "key": row.key,
            "priority": row.priority,
            "status": row.status,
            "prompt": row.prompt,
            "context": row.context,
            "created_at": row.created_at,
            "asked_at": row.asked_at,
            "answered_at": row.answered_at,
        }
        for row in rows
    ]
