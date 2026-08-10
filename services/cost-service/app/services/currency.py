"""Currency validation shared by ingestion, aggregation, and provider adapters."""

from __future__ import annotations

import re

_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")


def normalize_currency(value: object, *, required: bool = True) -> str:
    """Return a canonical ISO-4217 code or reject ambiguous provider data."""
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise ValueError("Provider response is missing a currency code")
        return "UNKNOWN"

    if not isinstance(value, str):
        raise ValueError("Currency code must be a three-letter string")

    currency = value.strip().upper()
    if not _CURRENCY_RE.fullmatch(currency):
        raise ValueError("Currency code must be a three-letter ISO code")
    return currency
