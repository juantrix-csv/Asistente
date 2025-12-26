from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from packages.agent_core.tools.calendar_tool import CalendarTool


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


def test_is_free_false_when_event(monkeypatch) -> None:
    tool = CalendarTool()
    monkeypatch.setattr(
        CalendarTool, "_get_service", lambda self: _FakeService(list_items=[{"id": "1"}])
    )

    start = datetime(2025, 1, 1, 10, 0, tzinfo=ZoneInfo("America/Argentina/Buenos_Aires"))
    end = start + timedelta(minutes=30)

    assert tool.is_free(start, end) is False