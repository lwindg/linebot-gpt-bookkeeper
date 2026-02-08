# -*- coding: utf-8 -*-
"""
Update intent helpers for GPT pipeline.
"""

import re
from typing import Optional

_UPDATE_KEYWORDS = ("修改", "更改", "改", "更新")
_UPDATE_FIELD_KEYWORDS = (
    "品項",
    "分類",
    "專案",
    "原幣金額",
    "金額",
    "原幣別",
    "幣別",
    "匯率",
    "付款方式",
    "明細說明",
    "明細",
    "必要性",
    "對象",
    "收款支付對象",
    "代墊狀態",
    "狀態",
)

_UPDATE_FIELD_PATTERN = re.compile(
    r"(?:修改|更改|改|更新)\s*(?P<field>品項|分類|專案|原幣金額|金額|原幣別|幣別|匯率|付款方式|明細說明|明細|必要性|對象|收款支付對象|代墊狀態|狀態)\s*(?:為|成)?\s*(?P<value>.+)$"
)
_UPDATE_FIELD_REVERSED_PATTERN = re.compile(
    r"(?P<field>品項|分類|專案|原幣金額|金額|原幣別|幣別|匯率|付款方式|明細說明|明細|必要性|對象|收款支付對象|代墊狀態|狀態)\s*(?:修改|更改|改|更新)\s*(?:為|成)?\s*(?P<value>.+)$"
)


def detect_update_intent(message: str) -> bool:
    text = message or ""
    return any(keyword in text for keyword in _UPDATE_KEYWORDS) and any(
        field in text for field in _UPDATE_FIELD_KEYWORDS
    )


def count_update_fields(message: str) -> int:
    """Count how many update fields are mentioned in the message, avoiding substring issues."""
    text = message or ""
    count = 0
    # Sort by length descending to match longest first (e.g., "原幣別" before "幣別")
    sorted_fields = sorted(_UPDATE_FIELD_KEYWORDS, key=len, reverse=True)
    for field in sorted_fields:
        if field in text:
            count += 1
            # Replace with placeholder to avoid matching substrings of what we already matched
            text = text.replace(field, "___")
    return count


def extract_update_fields_simple(message: str) -> Optional[dict]:
    """Try to extract update fields without GPT for simple patterns."""
    text = (message or "").strip()
    if not text:
        return None
    for pattern in (_UPDATE_FIELD_PATTERN, _UPDATE_FIELD_REVERSED_PATTERN):
        match = pattern.search(text)
        if not match:
            continue
        field = match.group("field").strip()
        value = match.group("value").strip()
        if value:
            return {field: value}
    return None
