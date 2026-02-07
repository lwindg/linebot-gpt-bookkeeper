# -*- coding: utf-8 -*-
"""
Amount and Currency Extraction (T008)

負責從文字中抽取金額與幣別。
支援格式：
- 標準格式：午餐 100
- 符號格式：午餐 $100
- 連寫格式：午餐100
- 貨幣前綴：USD 100, 日幣 1500
- 貨幣後綴：100 USD, 100 美金
"""

import re
from typing import Tuple

# 編譯正則表達式以提升效能
_CURRENCY_SYMBOLS = r"\$|USD|JPY|EUR|CNY|TWD|¥|円"
_CURRENCY_WORDS = r"美金|美元|日幣|日圓|日元|歐元|人民幣|台幣"
_CURRENCY_ALL = rf"{_CURRENCY_SYMBOLS}|{_CURRENCY_WORDS}"
_AMOUNT_PATTERN = re.compile(
    rf"({_CURRENCY_ALL})?\s*(-?\d+(?:\.\d+)?)\s*({_CURRENCY_ALL})?",
    re.IGNORECASE
)
# 日期格式 Pattern（需排除，避免將日期當作金額）
# 支援: 2024/1/15, 2024-01-15, 1/15, 01-15
_DATE_PATTERN = re.compile(
    r"(20\d{2}[/-]\d{1,2}[/-]\d{1,2}|"  # YYYY/MM/DD or YYYY-MM-DD
    r"\d{3}[/-]\d{1,2}[/-]\d{1,2}|"     # ROC YYY/MM/DD or YYY-MM-DD
    r"\d{1,2}[/-]\d{1,2})"               # MM/DD or MM-DD
)
# 時間格式 Pattern（需排除，避免將時間當作金額）
# 支援: HH:MM, HH:MM:SS
_TIME_PATTERN = re.compile(
    r"\b\d{1,2}:\d{2}(?::\d{2})?\b"
)

# 貨幣代碼對照表（支援中英文）
_CURRENCY_MAP = {
    "$": "TWD",
    "USD": "USD",
    "美金": "USD",
    "美元": "USD",
    "JPY": "JPY",
    "日幣": "JPY",
    "日圓": "JPY",
    "日元": "JPY",
    "¥": "JPY",
    "円": "JPY",
    "EUR": "EUR",
    "歐元": "EUR",
    "CNY": "CNY",
    "人民幣": "CNY",
    "TWD": "TWD",
    "台幣": "TWD",
}

# 用於偵測文字中貨幣關鍵字的 pattern（prefix 或 suffix）
_CURRENCY_KEYWORDS = tuple(_CURRENCY_MAP.keys())


def _detect_currency_in_text(text: str) -> str:
    """偵測文字中的貨幣關鍵字，回傳標準幣別代碼"""
    text_upper = text.upper()
    for keyword in _CURRENCY_KEYWORDS:
        if keyword.upper() in text_upper or keyword in text:
            return _CURRENCY_MAP.get(keyword, _CURRENCY_MAP.get(keyword.upper(), "TWD"))
    return "TWD"


def extract_amount_and_currency(text: str) -> Tuple[float, str, str]:
    """
    從文字中抽取金額與幣別。
    
    Args:
        text: 要解析的文字 (e.g., "午餐 100", "午餐$100", "午餐 100 USD")
    
    Returns:
        (amount, currency, remaining_text):
        - amount: 抽取出的金額 (float)，若無則為 0
        - currency: 幣別代碼 (str)，預設 "TWD"
        - remaining_text: 移除金額後的剩餘文字 (str)
    """
    if not text:
        return 0.0, "TWD", ""

    # 1. 排除日期與時間格式的數字
    matches = list(_AMOUNT_PATTERN.finditer(text))
    date_matches = list(_DATE_PATTERN.finditer(text))
    time_matches = list(_TIME_PATTERN.finditer(text))
    
    # 建立排除範圍集合
    exclude_spans = []
    for dm in date_matches:
        exclude_spans.append(dm.span())
    for tm in time_matches:
        exclude_spans.append(tm.span())
        
    if exclude_spans:
        def _overlaps_excluded(match_span: tuple[int, int]) -> bool:
            """檢查是否與日期/時間範圍重疊或完全被包含"""
            ms, me = match_span
            for es, ee in exclude_spans:
                # 完全包含或重疊
                if ms >= es and me <= ee:
                    return True
                # 部分重疊
                if (ms < ee and me > es):
                    return True
            return False
        
        matches = [m for m in matches if not _overlaps_excluded(m.span())]
    
    if not matches:
        return 0.0, "TWD", text

    # 2. 選擇最佳匹配
    # 如果有帶貨幣符號的，優先採用
    # 否則取最後一個數字（假設描述在前，金額在後）
    best_match = None
    for match in matches:
        prefix = match.group(1)
        suffix = match.group(3)
        if prefix or suffix:  # 有貨幣符號前綴或後綴，優先權高
            best_match = match
            break
    
    if not best_match:
        # 沒貨幣符號，取最後一個數字 (e.g. "買了 2 個便當 200" -> 取 200)
        best_match = matches[-1]

    # 3. 解析金額
    prefix = best_match.group(1)
    amount_str = best_match.group(2)
    suffix = best_match.group(3)
    try:
        amount = float(amount_str)
    except ValueError:
        return 0.0, "TWD", text

    # 4. 決定幣別
    currency = "TWD"
    if suffix:
        # 有後綴貨幣符號 (優先權高，處理如 $100 USD 或 $1000日圓)
        currency = _CURRENCY_MAP.get(suffix.upper(), _CURRENCY_MAP.get(suffix, "TWD"))
    elif prefix:
        # 有前綴貨幣符號
        currency = _CURRENCY_MAP.get(prefix.upper(), _CURRENCY_MAP.get(prefix, "TWD"))
    else:
        # 沒有前綴也沒後綴，檢查整句是否有貨幣關鍵字（可能是前面的中文）
        # e.g. "拉麵 日幣 1500" (若沒被 regex 抓到)
        currency = _detect_currency_in_text(text)

    # 5. 產生 remaining_text
    span = best_match.span()
    remaining = (text[:span[0]] + " " + text[span[1]:]).strip()
    # 移除多餘空白
    remaining = re.sub(r"\s+", " ", remaining).strip()

    return amount, currency, remaining
