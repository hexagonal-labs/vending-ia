"""Normalización determinista de descripciones de producto."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

_CONTENT = re.compile(r"\b(\d+(?:[.,]\d+)?)\s*(ml|cl|l|gr|g|kg)\b", re.IGNORECASE)
_PACK = re.compile(r"\b\d+\s*(?:x|\*)\s*\d+\b", re.IGNORECASE)
_FORMAT = re.compile(r"\b(lata|botella|brick|bolsa|barrita|pack)\b", re.IGNORECASE)
_WORDS_TO_IGNORE = frozenset({"de", "del", "con", "sin", "el", "la", "los", "las", "un", "una", "pack"})


@dataclass(frozen=True, slots=True)
class NormalizedProduct:
    raw_name: str
    normalized_name: str
    tokens: frozenset[str]
    content_value: Decimal | None
    content_unit: str | None
    format: str | None


def normalize_product_name(value: str) -> NormalizedProduct:
    normalized = _plain_text(value)
    content_value, content_unit = _content(normalized)
    product_format = _first_group(_FORMAT, normalized)
    without_metadata = _CONTENT.sub(" ", normalized)
    without_metadata = _PACK.sub(" ", without_metadata)
    tokens = frozenset(
        token
        for token in re.findall(r"[a-z0-9]+", without_metadata)
        if token not in _WORDS_TO_IGNORE and token != product_format
    )
    return NormalizedProduct(
        raw_name=value,
        normalized_name=" ".join(sorted(tokens)),
        tokens=tokens,
        content_value=content_value,
        content_unit=content_unit,
        format=product_format,
    )


def normalize_ean(value: str | None) -> str | None:
    if value is None:
        return None
    digits = "".join(character for character in value if character.isdigit())
    return digits if len(digits) in {8, 12, 13, 14} else None


def _plain_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.lower().replace("×", "x"))
    return "".join(character for character in decomposed if not unicodedata.combining(character))


def _content(value: str) -> tuple[Decimal | None, str | None]:
    match = _CONTENT.search(value)
    if match is None:
        return None, None
    try:
        number = Decimal(match.group(1).replace(",", "."))
    except InvalidOperation:
        return None, None
    unit = match.group(2).lower()
    if unit == "cl":
        return number * Decimal("10"), "ml"
    if unit == "l":
        return number * Decimal("1000"), "ml"
    if unit == "kg":
        return number * Decimal("1000"), "g"
    return number, "g" if unit in {"gr", "g"} else "ml"


def _first_group(expression: re.Pattern[str], value: str) -> str | None:
    match = expression.search(value)
    return match.group(1).lower() if match else None
