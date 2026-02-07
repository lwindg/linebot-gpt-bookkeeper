# -*- coding: utf-8 -*-
"""
Time Extraction (Task 5)

負責從文字中解析時間。
支援格式：HH:MM (e.g., 09:36, 14:20)
"""

import re
from typing import Optional

# Regex pattern for time format HH:MM or HH:MM:SS
_TIME_PATTERN = re.compile(r"\b(\d{1,2}):(\d{2})(?::(\d{2}))?\b")

def extract_time(text: str) -> Optional[str]:
    """
    從文字中解析時間，回傳 HH:MM:SS 格式字串。
    
    Args:
        text: 要解析的文字
    
    Returns:
        Formatted time string "HH:MM:SS" or None if no time found
    """
    if not text:
        return None
    
    match = _TIME_PATTERN.search(text)
    if not match:
        return None
        
    hour = int(match.group(1))
    minute = int(match.group(2))
    second = int(match.group(3)) if match.group(3) else 0
    
    # 驗證時間合法性
    if 0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59:
        return f"{hour:02d}:{minute:02d}:{second:02d}"
        
    return None

def clean_time_text(text: str) -> str:
    """
    從文字中移除時間關鍵字。
    
    Args:
        text: 原始文字
    
    Returns:
        cleaned_text: 移除時間後的文字
    """
    if not text:
        return ""
    
    # 使用與 extract_time 相同的 pattern 進行替換
    cleaned = _TIME_PATTERN.sub(' ', text)
    return re.sub(r'\s+', ' ', cleaned).strip()
