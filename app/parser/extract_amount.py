# -*- coding: utf-8 -*-
"""
Amount and Currency Extraction (T008)

負責從文字中抽取金額與幣別。
支援格式：
- 標準格式：午餐 100
- 符號格式：午餐 $100
- 連寫格式：午餐100
- 貨幣前綴：USD 100
"""

import re
from typing import Tuple

# 編譯正則表達式以提升效能
_AMOUNT_PATTERN = re.compile(r"(\$|USD|JPY|EUR|CNY|TWD)?\s*(-?\d+(?:\.\d+)?)")
_DATE_PATTERN = re.compile(r"(20\d{2}/\d{1,2}/\d{1,2}|\d{1,2}/\d{1,2})")
_CURRENCY_MAP = {
    "$": "TWD",
    "USD": "USD",
    "美金": "USD",
    "美元": "USD",
    "JPY": "JPY",
    "日幣": "JPY",
    "日圓": "JPY",
    "EUR": "EUR",
    "歐元": "EUR",
    "CNY": "CNY",
    "人民幣": "CNY",
    "TWD": "TWD",
    "台幣": "TWD",
}

def extract_amount_and_currency(text: str) -> Tuple[float, str, str]:
    """
    從文字中抽取金額與幣別。
    
    Args:
        text: 要解析的文字 (e.g., "午餐 100", "午餐$100")
    
    Returns:
        (amount, currency, remaining_text):
        - amount: 抽取出的金額 (float)，若無則為 0
        - currency: 幣別代碼 (str)，預設 "TWD"
        - remaining_text: 移除金額後的剩餘文字 (str)
    """
    if not text:
        return 0.0, "TWD", ""

    # 1. 嘗試比對數字 pattern
    # 搜尋字串中所有符合的數字，取最後一個（通常金額在後，或者避免誤判前面的數字）
    # 但依據 gpt_processor 邏輯，通常是找第一個明確的金額
    # 這裡採用搜尋第一個符合金額格式的策略
    
    matches = list(_AMOUNT_PATTERN.finditer(text))
    date_spans = [m.span() for m in _DATE_PATTERN.finditer(text)]
    if date_spans:
        def _in_date_span(span: tuple[int, int]) -> bool:
            return any(span[0] >= d[0] and span[1] <= d[1] for d in date_spans)

        matches = [m for m in matches if not _in_date_span(m.span())]
    if not matches:
        return 0.0, "TWD", text

    # 選擇邏輯：
    # 如果有帶貨幣符號的，優先採用
    # 否則取最後一個數字（假設描述在前，金額在後，如 "午餐 100"）
    # 若有負號，保留負號
    
    best_match = None
    for match in matches:
        prefix = match.group(1)
        if prefix: # 有貨幣符號，優先權高
            best_match = match
            break
    
    if not best_match:
        # 沒貨幣符號，取最後一個數字 (e.g. "買了 2 個便當 200" -> 取 200)
        best_match = matches[-1]

    # 解析金額
    prefix = best_match.group(1)
    amount_str = best_match.group(2)
    try:
        amount = float(amount_str)
    except ValueError:
        return 0.0, "TWD", text

    # 決定幣別
    currency = "TWD"
    if prefix:
        currency = _CURRENCY_MAP.get(prefix.upper(), "TWD")
    else:
        # 檢查文字中是否有其他貨幣關鍵字（e.g. "午餐 100 美金"）
        # 簡單檢查：移除金額後，檢查剩餘字串是否包含關鍵字
        pass # 暫時維持 TWD，若要支援後綴貨幣可在此擴充

    # 產生 remaining_text
    # 將 match 部分移除，並清理多餘空白
    span = best_match.span()
    remaining = (text[:span[0]] + " " + text[span[1]:]).strip()
    # 移除多餘空白
    remaining = re.sub(r"\s+", " ", remaining).strip()

    return amount, currency, remaining
