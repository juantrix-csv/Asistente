import pytest
from sqlalchemy import text

from packages.agent_core.core import handle_incoming_message
from packages.db.database import SessionLocal
from packages.db.models import MemoryChunk, MemoryFact, MessageRaw
from packages.memory.embeddings import OffEmbeddingProvider
from packages.memory.service import MemoryRetriever, ingest_messages
from packages.memory.tagger import extract_tags


def test_tagger_assigns_tags() -> None:
    tags = extract_tags("Necesito un flete y una camioneta")
    assert "fletes" in tags
    assert "camionetas" in tags


def test_ingest_messages_dedup(monkeypatch) -> None:
    monkeypatch.setenv("EMBEDDINGS_MODE", "off")
    with SessionLocal() as session:
        msg = MessageRaw(
            direction="inbound",
            platform="whatsapp",
            chat_id="123@c.us",
            sender_id="123@c.us",
            body="Necesito un flete",
            raw_payload={},
        )
        session.add(msg)
        session.commit()

        created_first = ingest_messages(session, since_hours=24, provider=OffEmbeddingProvider())
        created_second = ingest_messages(session, since_hours=24, provider=OffEmbeddingProvider())

        assert created_first == 1
        assert created_second == 0
        assert session.query(MemoryChunk).count() == 1


def test_retrieve_without_embeddings(monkeypatch) -> None:
    monkeypatch.setenv("EMBEDDINGS_MODE", "off")
    with SessionLocal() as session:
        chunk = MemoryChunk(
            source_type="manual",
            source_ref="note-1",
            chat_id="123@c.us",
            title="Flete",
            content="Servicio de flete confirmado",
            tags=["fletes"],
            topic="fletes",
            embedding=None,
        )
        session.add(chunk)
        session.commit()

        retriever = MemoryRetriever(session, provider=OffEmbeddingProvider())
        results = retriever.retrieve("flete", tags=["fletes"], chat_id="123@c.us", limit=5)
        assert len(results) == 1
        assert results[0].source_ref == "note-1"


def test_evidence_gate_missing_fact() -> None:
    reply = handle_incoming_message(
        chat_id="chat-1",
        sender_id="sender-1",
        text="agendame turno peluqueria en el lugar de siempre",
        sender_name="Juan",
        raw_payload={},
    )
    assert "de siempre" in reply.reply_text


def test_evidence_gate_fact_present() -> None:
    with SessionLocal() as session:
        fact = MemoryFact(
            subject="user",
            key="peluqueria_default",
            value="Peluqueria Central",
            confidence=80,
            source_ref="manual",
        )
        session.add(fact)
        session.commit()

    reply = handle_incoming_message(
        chat_id="chat-2",
        sender_id="sender-2",
        text="agendame turno peluqueria en el lugar de siempre",
        sender_name="Juan",
        raw_payload={},
    )
    assert "Peluqueria Central" in reply.reply_text


def test_ingest_and_search_end_to_end(monkeypatch) -> None:
    monkeypatch.setenv("EMBEDDINGS_MODE", "off")
    with SessionLocal() as session:
        msg = MessageRaw(
            direction="inbound",
            platform="whatsapp",
            chat_id="123@c.us",
            sender_id="123@c.us",
            body="Necesito un flete para manana",
            raw_payload={},
        )
        session.add(msg)
        session.commit()

        ingest_messages(session, since_hours=24, provider=OffEmbeddingProvider())
        retriever = MemoryRetriever(session, provider=OffEmbeddingProvider())
        results = retriever.retrieve("flete", tags=["fletes"], chat_id="123@c.us", limit=5)
        assert len(results) == 1
        assert results[0].content.startswith("Necesito un flete")


def test_pgvector_extension_available_or_skip() -> None:
    with SessionLocal() as session:
        result = session.execute(
            text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
        ).fetchall()
        if not result:
            pytest.skip("pgvector extension not available in test database")
        assert result[0][0] == "vector"
