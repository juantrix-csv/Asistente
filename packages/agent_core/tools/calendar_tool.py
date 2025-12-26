from __future__ import annotations

from datetime import datetime
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from packages.agent_core.tools.google_oauth import (
    GOOGLE_SCOPES,
    credentials_to_dict,
    has_token,
    load_token,
    save_token,
)
from packages.db.database import SessionLocal
from packages.db.models import ToolRun


class CalendarNotAuthorized(RuntimeError):
    pass


class CalendarTool:
    def __init__(
        self,
        calendar_id: str = "primary",
        log_runs: bool = True,
        audit_context: dict[str, Any] | None = None,
    ) -> None:
        self.calendar_id = calendar_id
        self.log_runs = log_runs
        self.audit_context = audit_context or {}

    def list_events(self, time_min: datetime, time_max: datetime) -> list[dict[str, Any]]:
        input_payload = {
            "time_min": time_min.isoformat(),
            "time_max": time_max.isoformat(),
        }

        try:
            service = self._get_service()
            events_result = (
                service.events()
                .list(
                    calendarId=self.calendar_id,
                    timeMin=time_min.isoformat(),
                    timeMax=time_max.isoformat(),
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            events = events_result.get("items", [])
            payload = [
                {
                    "id": event.get("id"),
                    "summary": event.get("summary"),
                    "start": event.get("start", {}).get("dateTime")
                    or event.get("start", {}).get("date"),
                    "end": event.get("end", {}).get("dateTime")
                    or event.get("end", {}).get("date"),
                    "location": event.get("location"),
                    "htmlLink": event.get("htmlLink"),
                }
                for event in events
            ]
            self._log_tool_run("calendar.list_events", input_payload, payload, "success")
            return payload
        except Exception as exc:
            self._log_tool_run(
                "calendar.list_events",
                input_payload,
                {"error": exc.__class__.__name__},
                "error",
            )
            raise

    def is_free(self, start: datetime, end: datetime) -> bool:
        input_payload = {"start": start.isoformat(), "end": end.isoformat()}
        events = self.list_events(start, end)
        is_free = len(events) == 0
        self._log_tool_run("calendar.is_free", input_payload, {"is_free": is_free}, "success")
        return is_free

    def create_event(
        self,
        title: str,
        start: datetime,
        end: datetime,
        location: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        input_payload = {
            "title": title,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "location": location,
            "notes": notes,
        }

        event_body: dict[str, Any] = {
            "summary": title,
            "start": {"dateTime": start.isoformat(), "timeZone": _tz_key(start)},
            "end": {"dateTime": end.isoformat(), "timeZone": _tz_key(end)},
        }
        if location:
            event_body["location"] = location
        if notes:
            event_body["description"] = notes

        try:
            service = self._get_service()
            event = (
                service.events()
                .insert(calendarId=self.calendar_id, body=event_body)
                .execute()
            )
            payload = {"event_id": event.get("id"), "htmlLink": event.get("htmlLink")}
            self._log_tool_run("calendar.create_event", input_payload, payload, "success")
            return payload
        except Exception as exc:
            self._log_tool_run(
                "calendar.create_event",
                input_payload,
                {"error": exc.__class__.__name__},
                "error",
            )
            raise

    def _get_service(self):
        credentials = self._get_credentials()
        return build("calendar", "v3", credentials=credentials, cache_discovery=False)

    def _get_credentials(self) -> Credentials:
        token_data = load_token()
        if not token_data:
            raise CalendarNotAuthorized("Missing Google OAuth token")

        credentials = Credentials.from_authorized_user_info(token_data, scopes=GOOGLE_SCOPES)
        if credentials.expired and not credentials.refresh_token:
            raise CalendarNotAuthorized("Expired Google OAuth token")
        if credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
                save_token(credentials_to_dict(credentials))
            except Exception as exc:
                raise CalendarNotAuthorized("Failed to refresh Google OAuth token") from exc
        return credentials

    def has_token(self) -> bool:
        return has_token()

    def _log_tool_run(
        self, tool_name: str, input_json: dict[str, Any], output_json: dict[str, Any], status: str
    ) -> None:
        if not self.log_runs:
            return
        with SessionLocal() as session:
            run = ToolRun(
                tool_name=tool_name,
                status=status,
                input_json=input_json,
                output_json=output_json,
                decision_source=self.audit_context.get("decision_source"),
                requested_by=self.audit_context.get("requested_by"),
                risk_level=self.audit_context.get("risk_level"),
                autonomy_mode_snapshot=self.audit_context.get("autonomy_mode_snapshot"),
            )
            session.add(run)
            session.commit()


def _tz_key(dt: datetime) -> str:
    tzinfo = dt.tzinfo
    if tzinfo is None:
        return "UTC"
    return getattr(tzinfo, "key", "UTC")
