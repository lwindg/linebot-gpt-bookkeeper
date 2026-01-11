# -*- coding: utf-8 -*-
"""
Payment method normalization utilities.

This module enforces canonical payment method names regardless of model output
synonyms (e.g. "灰狗卡" -> "FlyGo 信用卡").
"""

from __future__ import annotations


_PAYMENT_ALIASES: dict[str, str] = {
    "現金": "現金",
    "cash": "現金",
    "line": "Line 轉帳",
    "line轉帳": "Line 轉帳",
    "line bank": "Line 轉帳",
    "linebank": "Line 轉帳",
    "合庫": "合庫轉帳",
    "合庫轉帳": "合庫轉帳",
    "狗卡": "台新狗卡",
    "狗狗卡": "台新狗卡",
    "gogo": "台新狗卡",
    "狗": "台新狗卡",
    "richart": "台新 Richart",
    "台新richart": "台新 Richart",
    "台新 richart": "台新 Richart",
    "灰狗卡": "FlyGo 信用卡",
    "灰狗": "FlyGo 信用卡",
    "flygo": "FlyGo 信用卡",
    "fly go": "FlyGo 信用卡",
    "大戶": "大戶信用卡",
    "遠銀大戶": "大戶信用卡",
    "綠卡": "聯邦綠卡",
    "聯邦綠卡": "聯邦綠卡",
    "聯邦": "聯邦綠卡",
    "富邦": "富邦 Costco",
    "costco卡": "富邦 Costco",
    "costco": "富邦 Costco",
    "星展": "星展永續卡",
    "永續卡": "星展永續卡",
    "星展永續": "星展永續卡",
    "星展永續卡": "星展永續卡",
    "華南紅": "華南紅",
    "華南紅卡": "華南紅",
    "na": "NA",
    "n/a": "NA",
}


def normalize_payment_method(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return raw

    key = raw.lower().replace("　", " ").strip()
    key = " ".join(key.split())
    return _PAYMENT_ALIASES.get(key, raw)


_DETECT_ALIASES: tuple[tuple[str, str], ...] = (
    # Order matters: longer/more specific first.
    ("灰狗卡", "FlyGo 信用卡"),
    ("灰狗", "FlyGo 信用卡"),
    ("flygo", "FlyGo 信用卡"),
    ("fly go", "FlyGo 信用卡"),
    ("狗卡", "台新狗卡"),
    ("狗狗卡", "台新狗卡"),
    ("gogo", "台新狗卡"),
    ("richart", "台新 Richart"),
    ("台新 richart", "台新 Richart"),
    ("line轉帳", "Line 轉帳"),
    ("line bank", "Line 轉帳"),
    ("line", "Line 轉帳"),
    ("合庫轉帳", "合庫轉帳"),
    ("合庫", "合庫轉帳"),
    ("遠銀大戶", "大戶信用卡"),
    ("大戶", "大戶信用卡"),
    ("聯邦綠卡", "聯邦綠卡"),
    ("綠卡", "聯邦綠卡"),
    ("星展永續", "星展永續卡"),
    ("永續卡", "星展永續卡"),
    ("星展", "星展永續卡"),
    ("華南紅卡", "華南紅"),
    ("華南紅", "華南紅"),
    ("costco卡", "富邦 Costco"),
    ("costco", "富邦 Costco"),
    ("現金", "現金"),
)


def detect_payment_method(text: str) -> str | None:
    """
    Best-effort payment method detection from raw user message.

    This is intentionally conservative to avoid ambiguous short aliases (e.g. "狗").
    """

    haystack = (text or "").lower()
    if not haystack:
        return None

    for alias, canonical in _DETECT_ALIASES:
        if alias.lower() in haystack:
            return canonical
    return None
