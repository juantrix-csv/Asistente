from __future__ import annotations

import unicodedata

TAG_RULES = {
    "fletes": ["flete", "mudanza"],
    "camionetas": ["camioneta", "f100", "rastrojero"],
    "ascend": ["dietetica", "ascend"],
    "peluqueria": ["peluquer"],
    "agenda": ["turno", "agenda"],
}


def extract_tags(text: str | None) -> list[str]:
    if not text:
        return []
    folded = _fold_text(text)
    tags: list[str] = []
    for tag, keywords in TAG_RULES.items():
        if any(keyword in folded for keyword in keywords):
            tags.append(tag)
    return tags


def _fold_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return ascii_text.lower().strip()
