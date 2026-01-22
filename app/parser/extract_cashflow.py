# -*- coding: utf-8 -*-
"""
Cashflow Intent Extraction (T012)

負責辨識現金流意圖（轉帳、提款、繳費、收入）。
繼承 gpt_processor 的關鍵字邏輯。
"""

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
