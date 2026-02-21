# -*- coding: utf-8 -*-
"""Necessity normalization utilities.

This module keeps the Notion select vocabulary for "必要性" consistent.

Policy:
- For income-like transactions, necessity should be "N/A".
- Normalize common synonyms (e.g. "必須" -> "必要日常支出").
- If the value is unknown, fall back to a safe default.
"""

from __future__ import annotations

from typing import Optional


_ALLOWED = (
    "必要日常支出",
    "想吃想買但合理",
    "療癒性支出",
    "N/A",
)


_SYNONYMS: dict[str, str] = {
    "必須": "必要日常支出",
    "必要": "必要日常支出",
    "必需": "必要日常支出",
    "必需品": "必要日常支出",
    "n/a": "N/A",
    "na": "N/A",
}


def normalize_necessity(value: Optional[str], *, tx_type: Optional[str] = None) -> str:
    """Normalize necessity select value.

    Args:
        value: Raw value from model/user.
        tx_type: Ledger transaction type (e.g. "支出", "收入").

    Returns:
        Canonical necessity option.
    """

    if (tx_type or "").strip() == "收入":
        return "N/A"

    raw = (value or "").strip()
    if not raw:
        return "必要日常支出"

    mapped = _SYNONYMS.get(raw) or _SYNONYMS.get(raw.lower())
    if mapped:
        return mapped

    if raw in _ALLOWED:
        return raw

    # Unknown values: fall back conservatively.
    return "必要日常支出"
