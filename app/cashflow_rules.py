# -*- coding: utf-8 -*-
"""Cashflow intent helper rules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.payment_resolver import normalize_payment_method


@dataclass
class CashflowItem:
    """Normalized cashflow item extracted from GPT output."""

    intent: str
    item: str
    amount: float
    currency: str
    payment_method: str
    category: str
    date: Optional[str] = None


_ACCOUNT_ALIASES: tuple[tuple[str, str], ...] = (
    ("合庫", "合庫轉帳"),
    ("line", "Line 轉帳"),
    ("richart", "台新 Richart"),
    ("台新", "台新 Richart"),
    ("華南紅卡", "華南紅"),
    ("華南紅", "華南紅"),
    ("富邦", "富邦 Costco"),
    ("costco", "富邦 Costco"),
    ("大戶", "大戶信用卡"),
    ("遠銀", "大戶信用卡"),
    ("星展", "星展永續卡"),
    ("永續", "星展永續卡"),
    ("聯邦", "聯邦綠卡"),
    ("綠卡", "聯邦綠卡"),
    ("狗卡", "台新狗卡"),
    ("灰狗", "FlyGo 信用卡"),
)


def normalize_cashflow_payment_method(value: str) -> str:
    normalized = normalize_payment_method(value or "")
    return normalized or "NA"


def _detect_accounts(message: str) -> list[str]:
    text = (message or "").lower()
    hits: list[str] = []
    for alias, canonical in _ACCOUNT_ALIASES:
        if alias in text and canonical not in hits:
            hits.append(canonical)
    return hits


def infer_transfer_mode(message: str) -> str:
    """
    Infer transfer mode from user message.

    Returns:
        "person" or "account"
    """
    text = message or ""
    if any(token in text for token in ("轉給", "匯給", "付給", "給")):
        return "person"

    if any(token in text for token in ("轉到", "到", "轉入", "轉出")):
        if len(_detect_accounts(text)) >= 2:
            return "account"
        if any(token in text for token in ("帳戶", "帳號", "卡")):
            return "account"

    return "person"


def infer_transfer_accounts(message: str) -> tuple[Optional[str], Optional[str]]:
    accounts = _detect_accounts(message)
    if not accounts:
        return None, None
    if len(accounts) == 1:
        return accounts[0], None
    return accounts[0], accounts[1]
