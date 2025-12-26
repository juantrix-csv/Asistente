from fastapi.testclient import TestClient

import packages.agent_core.core as core
from apps.api.app.main import app
from packages.db.database import SessionLocal
from packages.db.models import ConversationState, MessageRaw, ToolRun

client = TestClient(app)


class _FakeRequest:
    def __init__(self, response):
        self._response = response

    def execute(self):
        return self._response


class _FakeEvents:
    def __init__(self, list_items, insert_response):
        self._list_items = list_items
        self._insert_response = insert_response

    def list(self, **kwargs):
        return _FakeRequest({"items": self._list_items})

    def insert(self, **kwargs):
        return _FakeRequest(self._insert_response)


class _FakeService:
    def __init__(self, list_items=None, insert_response=None):
        self._events = _FakeEvents(list_items or [], insert_response or {})

    def events(self):
        return self._events


def test_waha_webhook_agent_flow(monkeypatch) -> None:
    sent: list[str] = []

    def fake_send(self, chat_id: str, text: str) -> dict:
        sent.append(text)
        return {"messageId": f"fake-{len(sent)}"}

    monkeypatch.setattr(
        "apps.api.app.services.waha_client.WahaClient.send_text", fake_send
    )
    monkeypatch.setattr(core.CalendarTool, "has_token", lambda self: True)
    monkeypatch.setattr(
        core.CalendarTool,
        "_get_service",
        lambda self: _FakeService(
            list_items=[],
            insert_response={"id": "evt-1", "htmlLink": "http://example.com"},
        ),
    )

    payload = {
        "event": "message",
        "payload": {
            "chatId": "555@c.us",
            "author": "111@c.us",
            "body": "agendame reunion manana 16",
            "senderName": "Juan",
        },
    }

    response = client.post("/webhooks/waha", json=payload)
    assert response.status_code == 200

    duration_payload = {
        "event": "message",
        "payload": {
            "chatId": "555@c.us",
            "author": "111@c.us",
            "body": "60",
            "senderName": "Juan",
        },
    }

    response = client.post("/webhooks/waha", json=duration_payload)
    assert response.status_code == 200

    confirm_payload = {
        "event": "message",
        "payload": {
            "chatId": "555@c.us",
            "author": "111@c.us",
            "body": "confirmo",
            "senderName": "Juan",
        },
    }

    response = client.post("/webhooks/waha", json=confirm_payload)
    assert response.status_code == 200

    assert len(sent) == 3
    assert "Cuanto dura" in sent[0]
    assert "Confirmas" in sent[1]
    assert "evento creado" in sent[2]

    with SessionLocal() as session:
        state = session.get(ConversationState, "555@c.us")
        assert state is not None
        assert state.pending_action_json is None

        outbound_count = session.query(MessageRaw).filter_by(direction="outbound").count()
        assert outbound_count == 3

        tool_run = session.query(ToolRun).filter_by(tool_name="calendar.create_event").one()
        assert tool_run.status == "success"