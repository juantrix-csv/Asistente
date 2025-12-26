from datetime import datetime, timezone

from packages.db.database import SessionLocal
from packages.db.models import Contact
from packages.relations.threads import ThreadManager


def test_thread_manager_creates_and_updates() -> None:
    now = datetime.now(timezone.utc)
    with SessionLocal() as session:
        contact = Contact(chat_id="111@c.us", display_name="Proveedor")
        session.add(contact)
        session.commit()

        manager = ThreadManager(session)
        thread = manager.get_or_create_thread(contact.id)
        assert thread.status == "open"

        manager.record_inbound(thread, message_raw_id=1, text="Tenes horarios?", now=now, kind="question")
        assert thread.status == "waiting_me"

        manager.record_outbound(thread, message_raw_id=2, text="Te confirmo.", now=now, kind="info")
        assert thread.status == "open"


def test_thread_closes_on_closing_kind() -> None:
    now = datetime.now(timezone.utc)
    with SessionLocal() as session:
        contact = Contact(chat_id="222@c.us", display_name="Cliente")
        session.add(contact)
        session.commit()

        manager = ThreadManager(session)
        thread = manager.get_or_create_thread(contact.id)
        manager.record_inbound(thread, message_raw_id=3, text="ok", now=now, kind="closing")
        assert thread.status == "closed"
