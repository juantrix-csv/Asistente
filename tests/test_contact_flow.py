from datetime import datetime, timezone

from packages.agent_core.core import handle_incoming_message
from packages.db.database import SessionLocal
from packages.db.models import Contact, ConversationState, MessageRaw
from packages.relations.contact_handler import handle_contact_inbound


def test_contact_inbound_draft_and_confirm_send(monkeypatch) -> None:
    sent: dict[str, str] = {}

    def fake_send(self, chat_id: str, text: str) -> dict:
        sent["chat_id"] = chat_id
        sent["text"] = text
        return {"messageId": "fake"}

    monkeypatch.setattr(
        "apps.api.app.services.waha_client.WahaClient.send_text", fake_send
    )

    now = datetime.now(timezone.utc)
    with SessionLocal() as session:
        contact = Contact(
            chat_id="prov@c.us",
            display_name="Proveedor",
            trust_label="provider",
            trust_level=70,
            allow_auto_reply=False,
        )
        session.add(contact)
        inbound = MessageRaw(
            direction="inbound",
            platform="whatsapp",
            chat_id="prov@c.us",
            sender_id="prov@c.us",
            body="Tenes horarios para manana?",
            raw_payload={},
        )
        session.add(inbound)
        session.commit()

        result = handle_contact_inbound(
            session=session,
            chat_id="prov@c.us",
            message_raw_id=inbound.id,
            body=inbound.body,
            display_name=contact.display_name,
            user_chat_id="user@c.us",
            now=now,
        )
        session.commit()

    assert result.notify_user_text is not None

    with SessionLocal() as session:
        state = session.get(ConversationState, "user@c.us")
        assert state is not None
        assert state.pending_action_json["type"] == "message_send"

    reply = handle_incoming_message(
        chat_id="user@c.us",
        sender_id="user@c.us",
        text="confirmo",
        sender_name="User",
        raw_payload={},
    )

    assert "mensaje enviado" in reply.reply_text.lower()
    assert sent["chat_id"] == "prov@c.us"

    with SessionLocal() as session:
        outbound = (
            session.query(MessageRaw)
            .filter_by(direction="outbound", chat_id="prov@c.us")
            .one()
        )
        assert "confirmo" not in outbound.body.lower()
