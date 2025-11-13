# -*- coding: utf-8 -*-
"""
本地對照表模組

此模組提供固定的對照表（付款方式等），
用於減少 SYSTEM_PROMPT 的 token 消耗。

本地處理是「後處理」，在 GPT 回應後執行，
完全不影響 API 調用速度。
"""

# 付款方式標準化對照表
PAYMENT_METHODS = {
    # 現金
    "現金": "現金",
    "cash": "現金",
    "Cash": "現金",
    "CASH": "現金",

    # Line 轉帳
    "Line": "Line 轉帳",
    "line": "Line 轉帳",
    "LINE": "Line 轉帳",
    "Line轉帳": "Line 轉帳",
    "Line Bank": "Line 轉帳",
    "LineBank": "Line 轉帳",
    "linepay": "Line 轉帳",
    "LinePay": "Line 轉帳",

    # 合庫轉帳
    "合庫": "合庫轉帳",
    "合庫轉帳": "合庫轉帳",

    # 台新狗卡
    "狗卡": "台新狗卡",
    "狗狗卡": "台新狗卡",
    "GoGo": "台新狗卡",
    "gogo": "台新狗卡",
    "GOGO": "台新狗卡",
    "狗": "台新狗卡",

    # 台新 Richart
    "Richart": "台新 Richart",
    "richart": "台新 Richart",
    "台新Richart": "台新 Richart",
    "台新 Richart": "台新 Richart",

    # FlyGo 信用卡
    "灰狗卡": "FlyGo 信用卡",
    "灰狗": "FlyGo 信用卡",
    "FlyGo": "FlyGo 信用卡",
    "flygo": "FlyGo 信用卡",

    # 大戶信用卡
    "大戶": "大戶信用卡",
    "遠銀大戶": "大戶信用卡",
    "遠東大戶": "大戶信用卡",

    # 聯邦綠卡
    "綠卡": "聯邦綠卡",
    "聯邦綠卡": "聯邦綠卡",
    "聯邦": "聯邦綠卡",

    # 富邦 Costco
    "富邦": "富邦 Costco",
    "Costco卡": "富邦 Costco",
    "costco": "富邦 Costco",
    "Costco": "富邦 Costco",

    # 星展永續卡
    "星展": "星展永續卡",
    "永續卡": "星展永續卡",
    "星展永續": "星展永續卡",
}


def normalize_payment_method(method: str) -> str:
    """
    標準化付款方式名稱

    本函式在 GPT 回傳後執行（後處理），
    不會增加 API 調用延遲。

    Args:
        method: 原始付款方式名稱

    Returns:
        str: 標準化後的付款方式名稱

    Examples:
        >>> normalize_payment_method("狗卡")
        '台新狗卡'
        >>> normalize_payment_method("Line")
        'Line 轉帳'
        >>> normalize_payment_method("未知卡片")
        '未知卡片'  # 保持原樣
    """
    if not method:
        return method

    # 去除首尾空白
    method = method.strip()

    # 查找對照表
    standardized = PAYMENT_METHODS.get(method)

    if standardized:
        return standardized

    # 若找不到，保持原樣（可能是 GPT 識別的新付款方式）
    return method
