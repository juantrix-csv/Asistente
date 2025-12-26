from sqlalchemy import select

from packages.db.database import SessionLocal
from packages.db.models import MessageRaw


def test_migration_insert_select() -> None:
    with SessionLocal() as session:
        msg = MessageRaw(
            direction="inbound",
            platform="whatsapp",
            chat_id="999@c.us",
            sender_id="999@c.us",
            body="ping",
            raw_payload={},
        )
        session.add(msg)
        session.commit()

        result = session.execute(select(MessageRaw).where(MessageRaw.id == msg.id))
        loaded = result.scalar_one()
        assert loaded.body == "ping"