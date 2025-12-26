from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Iterable
from zoneinfo import ZoneInfo

from pgvector.sqlalchemy import cosine_distance
from sqlalchemy import or_, select

from packages.db.models import MemoryChunk, MessageRaw
from packages.memory.embeddings import EMBEDDING_DIM, EmbeddingProvider, get_embedding_provider
from packages.memory.tagger import extract_tags

logger = logging.getLogger(__name__)

TIMEZONE = ZoneInfo("America/Argentina/Buenos_Aires")


def ingest_messages(
    session,
    since_hours: int,
    chat_id: str | None = None,
    provider: EmbeddingProvider | None = None,
) -> int:
    since = datetime.now(TIMEZONE) - timedelta(hours=since_hours)
    base_query = session.query(MessageRaw).filter(MessageRaw.ts >= since)
    if chat_id:
        base_query = base_query.filter(MessageRaw.chat_id == chat_id)

    messages = base_query.order_by(MessageRaw.id.asc()).all()
    if not messages:
        return 0

    message_ids = [str(message.id) for message in messages]
    existing = (
        session.query(MemoryChunk.source_ref)
        .filter(
            MemoryChunk.source_type == "whatsapp_message",
            MemoryChunk.source_ref.in_(message_ids),
        )
        .all()
    )
    existing_refs = {row[0] for row in existing}

    new_messages = [message for message in messages if str(message.id) not in existing_refs]
    if not new_messages:
        return 0

    provider = provider or get_embedding_provider()
    contents = [message.body for message in new_messages if message.body]
    embeddings: list[list[float] | None] = [None] * len(contents)
    if provider.is_available() and contents:
        try:
            vectors = provider.embed_texts(contents)
            embeddings = _normalize_embeddings(vectors)
        except Exception:
            logger.warning("Embeddings unavailable, ingesting without vectors.")
            embeddings = [None] * len(contents)

    created = 0
    embedding_idx = 0
    for message in new_messages:
        if not message.body:
            continue
        tags = extract_tags(message.body)
        topic = tags[0] if tags else None
        vector = embeddings[embedding_idx] if embeddings else None
        embedding_idx += 1

        chunk = MemoryChunk(
            source_type="whatsapp_message",
            source_ref=str(message.id),
            chat_id=message.chat_id,
            title=None,
            content=message.body,
            tags=tags,
            topic=topic,
            embedding=vector,
        )
        session.add(chunk)
        created += 1

    session.commit()
    return created


class MemoryRetriever:
    def __init__(self, session, provider: EmbeddingProvider | None = None) -> None:
        self.session = session
        self.provider = provider or get_embedding_provider()

    def retrieve(
        self,
        query_text: str,
        tags: list[str] | None = None,
        chat_id: str | None = None,
        limit: int = 8,
    ) -> list[MemoryChunk]:
        tags = tags or []
        if self.provider.is_available() and query_text:
            try:
                vector = self.provider.embed_texts([query_text])[0]
                vector = _normalize_embeddings([vector])[0]
                stmt = select(MemoryChunk).where(MemoryChunk.embedding.is_not(None))
                if tags:
                    stmt = stmt.where(MemoryChunk.tags.overlap(tags))
                if chat_id:
                    stmt = stmt.where(MemoryChunk.chat_id == chat_id)
                stmt = stmt.order_by(cosine_distance(MemoryChunk.embedding, vector))
                return list(self.session.execute(stmt.limit(limit)).scalars())
            except Exception:
                logger.warning("Vector search unavailable, falling back to text search.")

        stmt = select(MemoryChunk)
        if tags:
            stmt = stmt.where(MemoryChunk.tags.overlap(tags))
        if chat_id:
            stmt = stmt.where(MemoryChunk.chat_id == chat_id)
        if query_text:
            pattern = f"%{query_text}%"
            stmt = stmt.where(
                or_(MemoryChunk.content.ilike(pattern), MemoryChunk.title.ilike(pattern))
            )
        stmt = stmt.order_by(MemoryChunk.created_at.desc())
        return list(self.session.execute(stmt.limit(limit)).scalars())


def _normalize_embeddings(vectors: Iterable[list[float]]) -> list[list[float]]:
    normalized: list[list[float]] = []
    for vector in vectors:
        if len(vector) == EMBEDDING_DIM:
            normalized.append(vector)
        elif len(vector) > EMBEDDING_DIM:
            normalized.append(vector[:EMBEDDING_DIM])
        else:
            padded = vector + [0.0] * (EMBEDDING_DIM - len(vector))
            normalized.append(padded)
    return normalized
