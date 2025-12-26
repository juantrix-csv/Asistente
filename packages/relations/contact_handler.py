from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from packages.db.database import SessionLocal
from packages.db.models import Contact, ConversationThread, ConversationState, ToolRun
from packages.relations.message_tools import build_reply_draft, send_message_and_store
from packages.relations.policy import ContactPolicy
from packages.relations.privacy import get_privacy_rules
from packages.relations.safety import MessageSafetyClassifier
from packages.relations.threads import ThreadManager
from packages.relations.trust import TrustEngine


@dataclass
class ContactInboundResult:
    notify_user_chat_id: str | None
    notify_user_text: str | None
    auto_reply_chat_id: str | None
    auto_reply_text: str | None
    thread_id: int | None
    outbound_kind: str | None


def handle_contact_inbound(
    session,
    chat_id: str,
    message_raw_id: int,
    body: str,
    display_name: str | None,
    user_chat_id: str | None,
    now: datetime,
) -> ContactInboundResult:
    contact = _get_or_create_contact(session, chat_id, display_name)
    contact.last_interaction_at = now.astimezone(timezone.utc)
    trust_engine = TrustEngine()
    if not contact.trust_label:
        trust_engine.apply_label(contact, "unknown")

    thread_manager = ThreadManager(session)
    thread = thread_manager.get_or_create_thread(contact.id)

    privacy_rules = get_privacy_rules(session)
    classifier = MessageSafetyClassifier()
    safety = classifier.classify(body, privacy_rules)

    inbound_kind = _inbound_kind(safety, thread)
    thread_manager.record_inbound(thread, message_raw_id, body, now, inbound_kind)

    if safety.closing and thread.status == "closed":
        session.commit()
        return ContactInboundResult(None, None, None, None, thread.id, None)

    if not safety.requires_response:
        session.commit()
        return ContactInboundResult(None, None, None, None, thread.id, None)

    draft = build_reply_draft(body, display_name or "Hola")
    policy = ContactPolicy(session)
    auto_allowed, _reason = policy.allow_auto_send(chat_id, draft)
    if safety.category == "sensitive":
        auto_allowed = False
    if auto_allowed and policy.autonomy_enabled("message_reply"):
        session.commit()
        return ContactInboundResult(
            notify_user_chat_id=None,
            notify_user_text=None,
            auto_reply_chat_id=chat_id,
            auto_reply_text=draft,
            thread_id=thread.id,
            outbound_kind=_outbound_kind(draft),
        )

    notify_text = _build_user_notification(display_name or chat_id, body, draft)
    pending_set = _set_pending_action(session, user_chat_id, chat_id, thread, draft)
    if not pending_set:
        notify_text = _build_user_notification(display_name or chat_id, body, None)
    session.commit()

    return ContactInboundResult(
        notify_user_chat_id=user_chat_id,
        notify_user_text=notify_text if user_chat_id else None,
        auto_reply_chat_id=None,
        auto_reply_text=None,
        thread_id=thread.id,
        outbound_kind=None,
    )


def send_contact_reply(
    thread_id: int,
    chat_id: str,
    text: str,
    outbound_kind: str,
    log_context: dict | None = None,
) -> bool:
    message_raw_id, _payload, error = send_message_and_store(chat_id, text)
    now = datetime.now(timezone.utc)
    with SessionLocal() as session:
        thread = session.query(ConversationThread).filter_by(id=thread_id).one_or_none()
        if thread is None:
            return False
        manager = ThreadManager(session)
        manager.record_outbound(thread, message_raw_id, text, now, outbound_kind)
        contact = session.query(Contact).filter_by(id=thread.contact_id).one_or_none()
        if contact:
            contact.last_interaction_at = now
        if log_context:
            run = ToolRun(
                tool_name="message.send",
                status="success" if error is None else "error",
                input_json={"chat_id": chat_id, "text": text},
                output_json={"sent": error is None},
                decision_source=log_context.get("decision_source"),
                requested_by=log_context.get("requested_by"),
                risk_level=log_context.get("risk_level"),
                autonomy_mode_snapshot=log_context.get("autonomy_mode_snapshot"),
            )
            session.add(run)
        session.commit()
    return error is None


def _get_or_create_contact(session, chat_id: str, display_name: str | None) -> Contact:
    contact = session.query(Contact).filter_by(chat_id=chat_id).one_or_none()
    if contact is None:
        contact = Contact(chat_id=chat_id, display_name=display_name)
        session.add(contact)
        session.flush()
        return contact
    if display_name and contact.display_name != display_name:
        contact.display_name = display_name
    return contact


def _build_user_notification(contact_name: str, body: str, draft: str | None) -> str:
    body_preview = _truncate(body)
    if draft:
        return (
            f"Mensaje de {contact_name}: \"{body_preview}\". "
            f"Borrador sugerido: \"{_truncate(draft)}\". "
            "Responde confirmo para enviar."
        )
    return f"Mensaje de {contact_name}: \"{body_preview}\"."


def _truncate(text: str, max_len: int = 160) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 3] + "..."


def _set_pending_action(
    session,
    user_chat_id: str | None,
    contact_chat_id: str,
    thread: ConversationThread,
    draft: str,
) -> bool:
    if not user_chat_id:
        return False
    state = session.get(ConversationState, user_chat_id)
    if state is None:
        state = ConversationState(chat_id=user_chat_id)
        session.add(state)
        session.flush()
    if state.pending_action_json:
        return False
    state.pending_action_json = {
        "type": "message_send",
        "payload": {
            "chat_id": contact_chat_id,
            "thread_id": thread.id,
            "text": draft,
        },
    }
    state.last_intent = "message_send"
    return True


def _inbound_kind(safety, thread: ConversationThread) -> str:
    if safety.closing:
        return "closing"
    if safety.contains_question:
        return "question"
    if thread.status == "waiting_them":
        return "answer"
    return "info"


def _outbound_kind(text: str) -> str:
    return "question" if "?" in text else "info"
