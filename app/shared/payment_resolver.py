# -*- coding: utf-8 -*-
"""
Payment method normalization utilities.

This module enforces canonical payment method names regardless of model output
synonyms (e.g. "灰狗卡" -> "FlyGo 信用卡").

v2.0: Now loads payment methods from YAML config file (app/config/payment_methods.yaml)
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml


@lru_cache(maxsize=1)
def _load_payment_aliases_from_yaml() -> dict[str, str]:
    """Load payment aliases from YAML config file."""
    config_path = Path(__file__).resolve().parents[1] / "config" / "payment_methods.yaml"
    if not config_path.exists():
        return _PAYMENT_ALIASES_LEGACY
    
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    if data and "aliases" in data:
        return {str(k).lower(): str(v) for k, v in data["aliases"].items()}
    return _PAYMENT_ALIASES_LEGACY


@lru_cache(maxsize=1)
def _load_detection_priority_from_yaml() -> tuple[tuple[str, str], ...]:
    """Load detection priority from YAML config file."""
    config_path = Path(__file__).resolve().parents[1] / "config" / "payment_methods.yaml"
    if not config_path.exists():
        return _DETECT_ALIASES_LEGACY
    
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    if data and "detection_priority" in data:
        return tuple((item["alias"], item["canonical"]) for item in data["detection_priority"])
    return _DETECT_ALIASES_LEGACY


# Legacy fallback (will be removed after migration verification)
_PAYMENT_ALIASES_LEGACY: dict[str, str] = {
    "現金": "現金",
    "cash": "現金",
    "line": "Line Pay",
    "line bank": "Line Pay",
    "linebank": "Line Pay",
    "linepay": "Line Pay",
    "line pay": "Line Pay",
    "合庫": "合庫",
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
    "日幣現金": "日圓現金",
    "日圓現金": "日圓現金",
    "円現金": "日圓現金",
    "na": "NA",
    "n/a": "NA",
}


def normalize_payment_method(value: str) -> str:
    """Normalize payment method to canonical name."""
    raw = (value or "").strip()
    if not raw:
        return raw

    key = raw.lower().replace("　", " ").strip()
    key = " ".join(key.split())
    aliases = _load_payment_aliases_from_yaml()
    return aliases.get(key, raw)


_DETECT_ALIASES_LEGACY: tuple[tuple[str, str], ...] = (
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
    ("line bank", "Line Pay"),
    ("line pay", "Line Pay"),
    ("linepay", "Line Pay"),
    ("line", "Line Pay"),
    ("合庫", "合庫"),
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
    ("日圓現金", "日圓現金"),
    ("日幣現金", "日圓現金"),
    ("円現金", "日圓現金"),
    ("現金", "現金"),
)


def detect_payment_method(text: str) -> str | None:
    """
    Best-effort payment method detection from raw user message.

    This is intentionally conservative to avoid ambiguous short aliases (e.g. "狗").
    v2.0: Now loads detection priority from YAML config.
    """

    haystack = (text or "").lower()
    if not haystack:
        return None

    detection_priority = _load_detection_priority_from_yaml()
    for alias, canonical in detection_priority:
        if alias.lower() in haystack:
            return canonical
    return None


def get_all_payment_keywords() -> list[str]:
    """
    取得所有付款方式關鍵字（用於品項文字清理）。
    
    Returns:
        list[str]: 所有付款方式別名關鍵字
    """
    aliases = _load_payment_aliases_from_yaml()
    detection_priority = _load_detection_priority_from_yaml()
    
    # 合併所有關鍵字
    keywords = set(aliases.keys())
    keywords.update(alias for alias, _ in detection_priority)
    
    # 加入標準名稱
    keywords.update(aliases.values())
    
    return list(keywords)


def get_keywords_for_payment_method(payment_method: str) -> list[str]:
    """
    取得與特定標準付款方式對應的關鍵字（別名 + 標準名稱）。

    Args:
        payment_method: 標準付款方式名稱（canonical）

    Returns:
        list[str]: 與該付款方式相關的關鍵字
    """
    if not payment_method:
        return []

    aliases = _load_payment_aliases_from_yaml()
    detection_priority = _load_detection_priority_from_yaml()
    canonical = payment_method.strip()

    keywords = set()
    for alias, mapped in aliases.items():
        if mapped == canonical:
            keywords.add(alias)
    for alias, mapped in detection_priority:
        if mapped == canonical:
            keywords.add(alias)
    keywords.add(canonical)

    return list(keywords)
