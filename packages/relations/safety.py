from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata


@dataclass(frozen=True)
class MessageSafety:
    category: str
    operational: bool
    requires_response: bool
    closing: bool
    contains_question: bool
    reason: str | None = None


class MessageSafetyClassifier:
    CLOSING = {"ok", "gracias", "listo", "\U0001F44D", "ok gracias", "joya"}
    QUESTION_WORDS = ("?", "cuando", "cuanto", "donde", "como", "podrias", "podes")
    OPERATIONAL_KEYWORDS = (
        "horario",
        "disponibilidad",
        "turno",
        "precio",
        "presupuesto",
        "cotizacion",
        "direccion",
        "pickup",
        "dropoff",
        "retiro",
        "entrega",
        "confirmo",
        "confirmas",
    )
    SENSITIVE_KEYWORDS = (
        "dni",
        "cbu",
        "alias",
        "tarjeta",
        "cuenta",
        "transfer",
        "pago",
        "reclamo",
        "queja",
        "problema",
        "salud",
        "historia clinica",
        "documento",
        "pasaporte",
        "mi casa",
        "mi domicilio",
        "domicilio",
    )

    def classify(self, text: str, privacy_rules: dict[str, bool]) -> MessageSafety:
        folded = _fold(text)
        closing = folded in self.CLOSING or _strip_punct(folded) in self.CLOSING
        if "\U0001F44D" in text:
            closing = True
        contains_question = "?" in text or any(word in folded for word in self.QUESTION_WORDS)
        sensitive = any(word in folded for word in self.SENSITIVE_KEYWORDS)

        if "direccion" in folded:
            if privacy_rules.get("no_share_address"):
                sensitive = True
            elif "mi casa" in folded or "mi domicilio" in folded:
                sensitive = True

        if privacy_rules.get("no_share_payment") and _mentions_payment(folded):
            sensitive = True

        operational = any(keyword in folded for keyword in self.OPERATIONAL_KEYWORDS)
        category = "sensitive" if sensitive else ("operational" if operational else "neutral")

        requires_response = False
        if not closing:
            requires_response = contains_question or _mentions_request(folded)

        reason = None
        if sensitive:
            reason = "sensitive"
        elif closing:
            reason = "closing"
        elif requires_response:
            reason = "needs_response"

        return MessageSafety(
            category=category,
            operational=operational,
            requires_response=requires_response,
            closing=closing,
            contains_question=contains_question,
            reason=reason,
        )


def _mentions_request(folded: str) -> bool:
    keywords = ("necesito", "preciso", "pasame", "pasame", "avisame", "avisa", "confirmas")
    return any(keyword in folded for keyword in keywords)


def _mentions_payment(folded: str) -> bool:
    return any(word in folded for word in ("pago", "transfer", "cbu", "alias", "tarjeta", "cuenta"))


def _fold(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_text.lower()).strip()


def _strip_punct(text: str) -> str:
    return re.sub(r"[^\w\s]", "", text).strip()
