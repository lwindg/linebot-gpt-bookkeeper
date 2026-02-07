# -*- coding: utf-8 -*-
"""
Date Extraction (T010)

負責從文字中解析日期。
支援格式（需位於每筆記帳開頭）：
- 明確日期：MM/DD (e.g., 01/23, 1/5)
- 完整日期：YYYY-MM-DD, YYYY/MM/DD (e.g., 2025-11-10)
- 民國日期：YYY/MM/DD, YYY-MM-DD (e.g., 115/02/06)
- 語義日期：今天、昨天、前天
"""

import re
from datetime import datetime, timedelta
from typing import Optional

# Regex patterns for date formats
# 1. YYYY-MM-DD or YYYY/MM/DD (完整日期格式，需在開頭)
_FULL_DATE_PATTERN = re.compile(r"^\s*(20\d{2})[/-](\d{1,2})[/-](\d{1,2})")
# 2. ROC date (YYY/MM/DD or YYY-MM-DD，需在開頭)
_ROC_DATE_PATTERN = re.compile(r"^\s*(\d{3})[/-](\d{1,2})[/-](\d{1,2})")
# 3. MM/DD or MM-DD (簡短日期格式，需在開頭)
_SHORT_DATE_PATTERN = re.compile(r"^\s*(\d{1,2})[/-](\d{1,2})(?!\d?月)")

def extract_date(text: str, context_date: datetime) -> Optional[str]:
    """
    從文字中解析日期，回傳 YYYY-MM-DD 格式字串。
    
    Args:
        text: 要解析的文字
        context_date: 參照日期 (通常為現在)
    
    Returns:
        Formatted date string "YYYY-MM-DD" or None if no date found
    """
    if not text:
        return None
    
    # 1. 優先檢查語義日期 ("昨天", "前天")
    # "今天" 通常省略，不需特別處理，由後端補上當日，或在此處明確回傳 YYYY-MM-DD
    
    semantic_date = _extract_semantic_date(text, context_date)
    if semantic_date:
        return semantic_date

    # 2. 優先檢查完整日期格式 (YYYY-MM-DD)
    full_date = _extract_full_date(text)
    if full_date:
        return full_date

    # 3. 檢查民國日期格式 (YYY/MM/DD)
    roc_date = _extract_roc_date(text)
    if roc_date:
        return roc_date

    # 4. 檢查簡短日期格式 (MM/DD)
    short_date = _extract_short_date(text, context_date)
    if short_date:
        return short_date
        
    return None


def _extract_semantic_date(text: str, context_date: datetime) -> Optional[str]:
    """解析語義日期關鍵字"""
    target = text.strip()
    if not target:
        return None

    if not re.match(r"^(前天|昨天|今天)", target):
        return None
    
    if "前天" in target:
        date = context_date - timedelta(days=2)
        return date.strftime("%Y-%m-%d")
        
    if "昨天" in target:
        date = context_date - timedelta(days=1)
        return date.strftime("%Y-%m-%d")

    # "今天" 視為當日，可選擇回傳明確日期或 None (讓系統預設)
    # 為了保持權威性，若使用者明確說 "今天"，我們就明確回傳日期
    if "今天" in target:
        return context_date.strftime("%Y-%m-%d")
        
    return None


def _extract_full_date(text: str) -> Optional[str]:
    """解析 YYYY-MM-DD 或 YYYY/MM/DD 格式日期"""
    match = _FULL_DATE_PATTERN.search(text)
    if not match:
        return None
        
    year = int(match.group(1))
    month = int(match.group(2))
    day = int(match.group(3))
    
    # 驗證日期合法性
    if 1 <= month <= 12 and 1 <= day <= 31:
        return f"{year:04d}-{month:02d}-{day:02d}"
        
    return None


def _extract_roc_date(text: str) -> Optional[str]:
    """解析民國 YYY-MM-DD 或 YYY/MM/DD 格式日期"""
    match = _ROC_DATE_PATTERN.search(text)
    if not match:
        return None

    roc_year = int(match.group(1))
    month = int(match.group(2))
    day = int(match.group(3))

    if 1 <= month <= 12 and 1 <= day <= 31:
        year = roc_year + 1911
        return f"{year:04d}-{month:02d}-{day:02d}"

    return None


def _extract_short_date(text: str, context_date: datetime) -> Optional[str]:
    """解析 MM/DD 或 MM-DD 格式日期（補當年）"""
    match = _SHORT_DATE_PATTERN.search(text)
    if not match:
        return None
        
    month = int(match.group(1))
    day = int(match.group(2))
    
    # 簡單驗證日期合法性
    if 1 <= month <= 12 and 1 <= day <= 31:
        return f"{context_date.year:04d}-{month:02d}-{day:02d}"
        
    return None
