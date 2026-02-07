# -*- coding: utf-8 -*-
"""Cashflow intent helper rules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.shared.payment_resolver import normalize_payment_method


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
    ("合庫", "合庫"),
    ("line bank", "Line Pay"),
    ("line pay", "Line Pay"),
    ("linepay", "Line Pay"),
    ("line", "Line Pay"),
    ("台新 Richart", "台新 Richart"),
    ("台新richart", "台新 Richart"),
    ("richart", "台新 Richart"),
    ("台新", "台新 Richart"),
    ("華南紅卡", "華南紅"),
    ("華南紅", "華南紅"),
    ("富邦 costco", "富邦 Costco"),
    ("costco卡", "富邦 Costco"),
    ("富邦", "富邦 Costco"),
    ("costco", "富邦 Costco"),
    ("大戶信用卡", "大戶信用卡"),
    ("遠銀大戶", "大戶信用卡"),
    ("大戶", "大戶信用卡"),
    ("遠銀", "大戶信用卡"),
    ("星展永續卡", "星展永續卡"),
    ("星展永續", "星展永續卡"),
    ("永續卡", "星展永續卡"),
    ("星展", "星展永續卡"),
    ("永續", "星展永續卡"),
    ("聯邦綠卡", "聯邦綠卡"),
    ("聯邦", "聯邦綠卡"),
    ("綠卡", "聯邦綠卡"),
    ("狗卡", "台新狗卡"),
    ("狗狗卡", "台新狗卡"),
    ("gogo", "台新狗卡"),
    ("灰狗卡", "FlyGo 信用卡"),
    ("灰狗", "FlyGo 信用卡"),
    ("flygo", "FlyGo 信用卡"),
    ("fly go", "FlyGo 信用卡"),
    ("日圓現金", "日圓現金"),
    ("日幣現金", "日圓現金"),
    ("円現金", "日圓現金"),
)


def normalize_cashflow_payment_method(value: str) -> str:
    normalized = normalize_payment_method(value or "")
    return normalized or "NA"


def _detect_accounts(message: str) -> list[str]:
    text = (message or "").lower()
    if not text:
        return []

    # 1. 找出所有別名（Alias）的所有匹配位置
    all_matches: list[tuple[int, int, str]] = []  # (start_index, end_index, canonical_name)
    for alias, canonical in _ACCOUNT_ALIASES:
        alias_lower = alias.lower()
        start_search = 0
        while True:
            idx = text.find(alias_lower, start_search)
            if idx == -1:
                break
            all_matches.append((idx, idx + len(alias_lower), canonical))
            start_search = idx + 1

    if not all_matches:
        return []

    # 2. 排序：先按起始位置排序，起始位置相同時，按長度降序（長的優先）
    all_matches.sort(key=lambda x: (x[0], -(x[1] - x[0])))

    # 3. 過濾重疊的匹配（採用貪婪策略，優先保留較早出現且較長的匹配）
    filtered_matches: list[tuple[int, int, str]] = []
    last_end = -1
    for start, end, canonical in all_matches:
        if start >= last_end:
            filtered_matches.append((start, end, canonical))
            last_end = end

    # 4. 依照出現順序返回 canonical name
    # 這裡保留重複項，例如「Richart轉到Richart」會得到 ["台新 Richart", "台新 Richart"]
    return [m[2] for m in filtered_matches]


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
        # 如果偵測到兩個不同的帳戶，或是明確提到帳戶關鍵字
        accounts = _detect_accounts(text)
        if len(set(accounts)) >= 2:
            return "account"
        if any(token in text for token in ("帳戶", "帳號", "卡")):
            return "account"

    return "person"


def infer_transfer_accounts(message: str) -> tuple[Optional[str], Optional[str]]:
    accounts = _detect_accounts(message)
    if not accounts:
        return None, None
    
    # 取第一個偵測到的帳戶作為來源
    source = accounts[0]
    target = None
    
    # 尋找與來源不同的第二個帳戶作為目標
    for i in range(1, len(accounts)):
        if accounts[i] != source:
            target = accounts[i]
            break
            
    return source, target
