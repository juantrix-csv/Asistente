from fastapi.testclient import TestClient

from apps.api.app.main import app
from packages.db.database import SessionLocal
from packages.db.models import Contact, MessageRaw

client = TestClient(app)


def test_waha_webhook_persists_and_sends(monkeypatch) -> None:
    sent: dict[str, str] = {}

    def fake_send(self, chat_id: str, text: str) -> dict:
        sent["chat_id"] = chat_id
        sent["text"] = text
        return {"messageId": "fake"}

    monkeypatch.setattr(
        "apps.api.app.services.waha_client.WahaClient.send_text", fake_send
    )

    payload = {
        "event": "message",
        "payload": {
            "chatId": "123@c.us",
            "author": "111@c.us",
            "body": "hola",
            "senderName": "Juan",
        },
    }

    response = client.post("/webhooks/waha", json=payload)

    assert response.status_code == 200
    assert sent["chat_id"] == "123@c.us"
    assert sent["text"] == "Recibi tu mensaje"

    with SessionLocal() as session:
        inbound = session.query(MessageRaw).filter_by(direction="inbound").one()
        outbound = session.query(MessageRaw).filter_by(direction="outbound").one()
        contact = session.query(Contact).filter_by(chat_id="123@c.us").one()

        assert inbound.body == "hola"
        assert outbound.body == "Recibi tu mensaje"
        assert contact.display_name == "Juan"
