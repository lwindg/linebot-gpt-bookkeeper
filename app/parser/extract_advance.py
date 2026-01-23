# -*- coding: utf-8 -*-
"""
Advance Payment Status Extraction (T011)

負責從文字中抽取代墊狀態與對象。
Logic based on app/prompts.py (v1.5.0 rules)

| 代墊狀態 | 關鍵字組合 | 範例訊息 |
|---------|----------|---------|
| **代墊** | 「代/幫」+對象+「買/付/墊/代墊」 | 代妹買、代妹付、幫同事墊付、幫同事代墊、幫媽墊 |
| **需支付** | 對象+「代訂/代付/幫買/先墊」（不含「幫+對象+付/墊付」） | 弟代訂、妹代付、朋友幫買、同事先墊 |
| **不索取** | 包含「不用還」、「不索取」、「送給」 | 幫媽買藥不用還、送給弟 |
| **無** | **完全沒有**上述關鍵字 | 午餐120元現金 |
"""

import re
from typing import Tuple

# Regex patterns derived from prompt rules
# 注意順序：先判斷「不索取」，再判斷「代墊」（我付），最後判定「需支付」（別人付）

# 1. 不索取
_NO_CLAIM_KEYWORDS = ("不用還", "不索取", "送給", "請客", "我請")
# Pattern for "請 + 對象 + 喝/吃/..." (e.g. 請同事喝飲料)
_NO_CLAIM_PATTERN = re.compile(r"請(?P<who>.+?)(?:喝|吃|午餐|晚餐|早餐)")

# 2. 代墊 (I paid for someone)
# Pattern: (幫|代) + (Who) + (買|付|墊|代墊|墊付)
# Exclusion: need to ensure it's not "別人幫買" (which is 需支付)
_ADVANCE_PAID_PATTERN = re.compile(r"(?:幫|代)(?P<who>.+?)(?:買|付|墊|代墊|墊付)")

# 3. 需支付 (Someone paid for me)
# Pattern: (Who) + (代訂|代付|幫買|先墊)
# Exclusion: pattern MUST NOT start with "幫" (handled by above)
_ADVANCE_DUE_PATTERN = re.compile(r"(?P<who>.+?)(?:代訂|代付|幫買|先墊)")


def extract_advance_status(text: str) -> Tuple[str, str]:
    """
    從文字中抽取代墊狀態與對象。
    
    Args:
        text: 要解析的文字
    
    Returns:
        (status, counterparty):
        - status: "無" | "代墊" | "需支付" | "不索取"
        - counterparty: 對象名稱 (e.g., "同事", "妹")，若無則為空字串
    """
    raw = text.strip()
    if not raw:
        return "無", ""
        
    # 1. 偵測「不索取」
    if any(k in raw for k in _NO_CLAIM_KEYWORDS):
        return "不索取", ""
    
    # 1b. 偵測「請+對象+喝/吃」pattern (e.g. 請同事喝飲料)
    no_claim_match = _NO_CLAIM_PATTERN.search(raw)
    if no_claim_match:
        return "不索取", ""

    # 2. 偵測「代墊」（我先付）
    # 規則：「代/幫」+對象+「買/付/墊/代墊」
    # e.g. "幫同事墊付" -> who="同事"
    match = _ADVANCE_PAID_PATTERN.search(raw)
    if match:
        who = match.group("who").strip()
        # 簡單過濾：對象不應太長（避免誤判整個句子）
        if who and len(who) <= 10:
             return "代墊", who

    # 3. 偵測「需支付」（別人先付）
    # 規則：對象+「代訂/代付/幫買/先墊」
    # e.g. "同事先墊" -> who="同事"
    # 注意：需排除 "我幫同事代付" 這種情況（已被上方規則捕獲，但若上方未捕獲需小心）
    # 此處邏輯：若上方未捕獲，且不以 "幫" 開頭（雖 Regex 已隱含，但多重確認）
    match_due = _ADVANCE_DUE_PATTERN.search(raw)
    if match_due:
        who = match_due.group("who").strip()
        # 排除 "我" 開頭的情況 (e.g. "我幫買" -> 應是代墊，但這裡可能誤判 "我" 為對象)
        # 不過 "我幫買" 會先符合 _ADVANCE_PAID_PATTERN ("幫買") ?? 
        # _ADVANCE_PAID_PATTERN 需要 "幫" 開頭
        
        # 加強過濾：若 who 包含 "幫" 字，可能是誤判 (e.g. "幫同事幫買" -> 奇怪的句法)
        if "幫" not in who and len(who) <= 10:
             return "需支付", who

    return "無", ""

