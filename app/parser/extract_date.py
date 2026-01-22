# -*- coding: utf-8 -*-
"""
Date Extraction (T010)

負責從文字中解析日期。
支援格式：
- 明確日期：MM/DD (e.g., 01/23, 1/5)
- 語義日期：今天、昨天、前天
"""

import re
from datetime import datetime, timedelta
from typing import Optional

# Regex pattern for MM/DD format
# 支援 1/5, 01/23, 12/31, 11/1 等格式
_DATE_PATTERN = re.compile(r"(\d{1,2})[/-](\d{1,2})")

def extract_date(text: str, context_date: datetime) -> Optional[str]:
    """
    從文字中解析日期，回傳 MM/DD 格式字串。
    
    Args:
        text: 要解析的文字
        context_date: 參照日期 (通常為現在)
    
    Returns:
        Formatted date string "MM/DD" or None if no date found
    """
    if not text:
        return None
    
    # 1. 優先檢查語義日期 ("昨天", "前天")
    # "今天" 通常省略，不需特別處理，由後端補上當日，或在此處明確回傳 MM/DD
    
    semantic_date = _extract_semantic_date(text, context_date)
    if semantic_date:
        return semantic_date

    # 2. 檢查明確日期格式 (MM/DD)
    explicit_date = _extract_explicit_date(text)
    if explicit_date:
        return explicit_date
        
    return None


def _extract_semantic_date(text: str, context_date: datetime) -> Optional[str]:
    """解析語義日期關鍵字"""
    target = text.strip()
    
    if "前天" in target:
        date = context_date - timedelta(days=2)
        return date.strftime("%m/%d")
        
    if "昨天" in target:
        date = context_date - timedelta(days=1)
        return date.strftime("%m/%d")

    # "今天" 視為當日，可選擇回傳明確日期或 None (讓系統預設)
    # 為了保持權威性，若使用者明確說 "今天"，我們就明確回傳日期
    if "今天" in target:
        return context_date.strftime("%m/%d")
        
    return None


def _extract_explicit_date(text: str) -> Optional[str]:
    """解析 MM/DD 格式日期"""
    match = _DATE_PATTERN.search(text)
    if not match:
        return None
        
    month = int(match.group(1))
    day = int(match.group(2))
    
    # 簡單驗證日期合法性
    if 1 <= month <= 12 and 1 <= day <= 31:
        return f"{month:02d}/{day:02d}"
        
    return None
