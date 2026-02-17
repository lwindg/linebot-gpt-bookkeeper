# -*- coding: utf-8 -*-
"""
Payment Method Extraction (T009)

負責從文字中優先抽取付款方式。
依賴 `app.shared.payment_resolver` 的設定。
"""

import re
from typing import Optional, Tuple
from app.shared.payment_resolver import (
    detect_payment_method,
    normalize_payment_method,
    get_keywords_for_payment_method,
)

def extract_payment_method(text: str) -> str:
    """
    從文字中抽取付款方式。
    
    Args:
        text: 要解析的文字
    
    Returns:
        canonical_payment_method: 標準化後的付款方式名稱，若無則回傳 "N/A"
    """
    # 使用 payment_resolver 的偵測邏輯（已包含優先序與別名對照）
    detected = detect_payment_method(text)
    
    if detected:
        return detected # detect_payment_method 已經回傳 canonical name
        
    return "N/A"


def clean_item_text(text: str, payment_method: str) -> str:
    """
    從品項文字中移除付款方式關鍵字。
    
    Args:
        text: 原始品項文字
        payment_method: 已偵測到的標準付款方式名稱
    
    Returns:
        cleaned_text: 移除付款關鍵字後的品項文字
    
    Examples:
        >>> clean_item_text("午餐 現金", "現金")
        '午餐'
        >>> clean_item_text("早餐 元 Line Pay", "Line Pay")
        '早餐'
    """
    if not text:
        return ""
    
    cleaned = text
    # 先移除開頭日期（避免品項包含日期片段）
    for pattern in (
        r'^\s*20\d{2}[/-]\d{1,2}[/-]\d{1,2}',
        r'^\s*\d{3}[/-]\d{1,2}[/-]\d{1,2}',
        r'^\s*\d{1,2}[/-]\d{1,2}(?!\d?月)',
    ):
        if re.match(pattern, cleaned):
            cleaned = re.sub(pattern, ' ', cleaned, count=1)
            break
    # 再處理通用的「元」與空白（即使沒有付款方式也要清理）
    cleaned = re.sub(r'\s+', ' ', cleaned)
    cleaned = re.sub(r'\s*元\s*$', '', cleaned)  # 移除結尾的「元」
    cleaned = re.sub(r'^\s*元\s*', '', cleaned)  # 移除開頭的「元」
    
    if payment_method == "N/A":
        return cleaned.strip()
    
    # 僅移除與偵測到的付款方式相關的關鍵字
    scoped_keywords = get_keywords_for_payment_method(payment_method)
    
    # 處理複合付款方式可能被金額解析器部分消耗的情況 (e.g. "日圓現金" 被吃掉 "日圓" 剩下 "現金")
    if payment_method in ("日圓現金", "Suica"):
        for extra in ["現金", "cash", "日圓", "日幣", "円", "suica"]:
            if extra not in scoped_keywords:
                scoped_keywords.append(extra)
    
    sorted_keywords = sorted(scoped_keywords, key=len, reverse=True)
    
    # 付款方式關鍵字清理
    for keyword in sorted_keywords:
        # 使用 word boundary 或空格分隔來避免誤刪（如 "line" 在 "deadline" 中）
        # 對於中文關鍵字直接替換，對於英文使用 word boundary
        if re.match(r'^[a-zA-Z\s]+$', keyword):
            # 英文關鍵字：case-insensitive word boundary
            pattern = re.compile(r'\b' + re.escape(keyword) + r'\b', re.IGNORECASE)
        else:
            # 中文或混合：直接替換
            pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        
        cleaned = pattern.sub('', cleaned)
    
    # 清理多餘空格和「元」字
    cleaned = re.sub(r'\s+', ' ', cleaned)
    cleaned = re.sub(r'\s*元\s*$', '', cleaned)  # 移除結尾的「元」
    cleaned = re.sub(r'^\s*元\s*', '', cleaned)  # 移除開頭的「元」
    
    return cleaned.strip()
