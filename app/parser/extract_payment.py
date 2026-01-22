# -*- coding: utf-8 -*-
"""
Payment Method Extraction (T009)

負責從文字中優先抽取付款方式。
依賴 `app.payment_resolver` 的設定。
"""

from typing import Optional
from app.payment_resolver import detect_payment_method, normalize_payment_method

def extract_payment_method(text: str) -> str:
    """
    從文字中抽取付款方式。
    
    Args:
        text: 要解析的文字
    
    Returns:
        canonical_payment_method: 標準化後的付款方式名稱，若無則回傳 "NA"
    """
    # 使用 payment_resolver 的偵測邏輯（已包含優先序與別名對照）
    detected = detect_payment_method(text)
    
    if detected:
        return detected # detect_payment_method 已經回傳 canonical name
        
    return "NA"
