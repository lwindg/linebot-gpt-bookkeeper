# -*- coding: utf-8 -*-
"""
Cashflow Intent Extraction (T012)

負責辨識現金流意圖（轉帳、提款、繳費、收入）。
繼承 gpt_processor 的關鍵字邏輯。
"""

import re
from typing import Optional, Tuple
from app.cashflow_rules import infer_transfer_accounts

# 現金流關鍵字定義
_CASHFLOW_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("card_payment", ("繳卡費", "信用卡費", "繳信用卡")),
    ("transfer", ("轉帳", "匯款", "轉入", "轉出")),
    ("withdrawal", ("提款", "領現", "領錢", "ATM")),
    ("income", ("收入", "入帳", "薪水", "退款", "退費", "收款")),
)

def detect_cashflow_intent(text: str) -> Optional[str]:
    """
    偵測現金流意圖。
    
    Args:
        text: 要分析的文字
    
    Returns:
        intent_type (str): 'transfer', 'card_payment', 'withdrawal', 'income' 或 None
    """
    if not text:
        return None

    # 換匯/換幣：只有在可辨識出來源與目標帳戶時，才視為 transfer，
    # 避免把一般語句（例如「換新鞋」）誤判為現金流。
    if any(keyword in text for keyword in ("換", "兌換", "換成", "轉成")):
        source, target = infer_transfer_accounts(text)
        if source and target:
            return "transfer"
        
    for intent_type, keywords in _CASHFLOW_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return intent_type
    return None

def extract_transfer_accounts(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    抽取轉帳/繳費帳戶。
    
    Returns:
        (source_account, target_account)
    """
    return infer_transfer_accounts(text)


_EXCHANGE_PATTERN = re.compile(
    r"(?P<source_amount>-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)"
    r"\s*(?P<source_currency>twd|ntd|nt\$|台幣|元)?"
    r"\s*(?:換|兌換|換成|轉成)\s*"
    r".*?"
    r"(?P<target_amount>-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)"
    r"\s*(?P<target_currency>btc|bitcoin|xbt|比特幣)?",
    re.IGNORECASE,
)


def _normalize_currency_token(token: Optional[str]) -> Optional[str]:
    if not token:
        return None
    t = token.strip().lower()
    if t in {"twd", "ntd", "nt$", "台幣", "元"}:
        return "TWD"
    if t in {"btc", "bitcoin", "xbt", "比特幣"}:
        return "BTC"
    return None


def extract_exchange_transfer_details(
    text: str,
    *,
    target_account: Optional[str] = None,
) -> Tuple[Optional[float], Optional[str], Optional[float], Optional[str]]:
    """
    從「A 金額 換 B 金額」格式抽出來源/目標金額與幣別。

    目前用於現金流轉帳的加密資產兌換情境，例如：
    - MAX 4294.712 換比特幣 0.002
    """
    if not text:
        return None, None, None, None
    if not any(k in text for k in ("換", "兌換", "換成", "轉成")):
        return None, None, None, None

    m = _EXCHANGE_PATTERN.search(text)
    if not m:
        return None, None, None, None

    try:
        source_amount = float(m.group("source_amount").replace(",", ""))
        target_amount = float(m.group("target_amount").replace(",", ""))
    except ValueError:
        return None, None, None, None

    if source_amount <= 0 or target_amount <= 0:
        return None, None, None, None

    source_currency = _normalize_currency_token(m.group("source_currency")) or "TWD"
    target_currency = _normalize_currency_token(m.group("target_currency"))
    if not target_currency and target_account == "比特幣":
        target_currency = "BTC"
    if not target_currency:
        target_currency = source_currency

    return source_amount, source_currency, target_amount, target_currency
