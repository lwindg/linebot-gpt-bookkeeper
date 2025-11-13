# -*- coding: utf-8 -*-
"""
本地日期解析模組

此模組在 GPT 處理前先用正則表達式提取日期，
確保日期解析的準確性和可靠性。
"""

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Tuple, Optional


def parse_date_from_message(message: str) -> Tuple[str, Optional[str], Optional[str]]:
    """
    從用戶訊息中提取並解析日期與時間

    支援格式：
    - "11/12" → "2025-11-12"（M/D 格式，補上當前年份）
    - "2025/11/12" → "2025-11-12"（Y/M/D 格式）
    - "11月12日" → "2025-11-12"（中文日期，補上當前年份）
    - "2025年11月12日" → "2025-11-12"（完整中文日期）
    - "今天" → 當天日期
    - "昨天" → 前一天日期
    - "11/12 14:30" → 日期 + 時間

    Args:
        message: 用戶訊息原文

    Returns:
        Tuple[str, Optional[str], Optional[str]]: (處理後的訊息, 解析的日期 YYYY-MM-DD, 解析的時間 HH:MM)

    Examples:
        >>> parse_date_from_message("11/12 午餐 200 現金")
        ("午餐 200 現金", "2025-11-12", None)
        >>> parse_date_from_message("11月11日早餐50現金")
        ("早餐50現金", "2025-11-11", None)
        >>> parse_date_from_message("11/12 14:30 午餐 200 現金")
        ("午餐 200 現金", "2025-11-12", "14:30")
        >>> parse_date_from_message("午餐 200 現金")
        ("午餐 200 現金", None, None)
    """
    taipei_tz = ZoneInfo('Asia/Taipei')
    now = datetime.now(taipei_tz)
    today = now.date()

    parsed_date = None
    parsed_time = None
    remaining_message = message

    # 模式 1：「今天」
    if '今天' in message:
        parsed_date = today.strftime("%Y-%m-%d")
        remaining_message = message.replace('今天', '').strip()
        return (remaining_message, parsed_date, parsed_time)

    # 模式 2：「昨天」
    if '昨天' in message:
        yesterday = today - timedelta(days=1)
        parsed_date = yesterday.strftime("%Y-%m-%d")
        remaining_message = message.replace('昨天', '').strip()
        return (remaining_message, parsed_date, parsed_time)

    # 模式 3：「YYYY年M月D日 HH:MM」或「M月D日 HH:MM」（中文日期 + 時間）
    pattern_cn_with_time = r'(?:(\d{4})年)?(\d{1,2})月(\d{1,2})日?\s+(\d{1,2}):(\d{2})'
    match = re.search(pattern_cn_with_time, message)
    if match:
        year_str = match.group(1)
        month = int(match.group(2))
        day = int(match.group(3))
        hour = int(match.group(4))
        minute = int(match.group(5))

        # 補上年份
        year = int(year_str) if year_str else today.year

        parsed_date = f"{year:04d}-{month:02d}-{day:02d}"
        parsed_time = f"{hour:02d}:{minute:02d}"

        # 從訊息中移除日期時間部分
        remaining_message = message[:match.start()] + message[match.end():]
        remaining_message = remaining_message.strip()

        return (remaining_message, parsed_date, parsed_time)

    # 模式 4：「YYYY年M月D日」或「M月D日」（中文日期，無時間）
    pattern_cn_date_only = r'(?:(\d{4})年)?(\d{1,2})月(\d{1,2})日?(?!\d)'
    match = re.search(pattern_cn_date_only, message)
    if match:
        year_str = match.group(1)
        month = int(match.group(2))
        day = int(match.group(3))

        # 補上年份
        year = int(year_str) if year_str else today.year

        parsed_date = f"{year:04d}-{month:02d}-{day:02d}"

        # 從訊息中移除日期部分
        remaining_message = message[:match.start()] + message[match.end():]
        remaining_message = remaining_message.strip()

        return (remaining_message, parsed_date, parsed_time)

    # 模式 5：「YYYY/M/D HH:MM」或「M/D HH:MM」（日期 + 時間）
    pattern_with_time = r'(?:(\d{4})/)?(\d{1,2})/(\d{1,2})\s+(\d{1,2}):(\d{2})'
    match = re.search(pattern_with_time, message)
    if match:
        year_str = match.group(1)
        month = int(match.group(2))
        day = int(match.group(3))
        hour = int(match.group(4))
        minute = int(match.group(5))

        # 補上年份
        year = int(year_str) if year_str else today.year

        parsed_date = f"{year:04d}-{month:02d}-{day:02d}"
        parsed_time = f"{hour:02d}:{minute:02d}"

        # 從訊息中移除日期時間部分
        remaining_message = message[:match.start()] + message[match.end():]
        remaining_message = remaining_message.strip()

        return (remaining_message, parsed_date, parsed_time)

    # 模式 6：「YYYY/M/D」或「M/D」（只有日期）
    pattern_date_only = r'(?:(\d{4})/)?(\d{1,2})/(\d{1,2})(?!\d)'
    match = re.search(pattern_date_only, message)
    if match:
        year_str = match.group(1)
        month = int(match.group(2))
        day = int(match.group(3))

        # 補上年份
        year = int(year_str) if year_str else today.year

        parsed_date = f"{year:04d}-{month:02d}-{day:02d}"

        # 從訊息中移除日期部分
        remaining_message = message[:match.start()] + message[match.end():]
        remaining_message = remaining_message.strip()

        return (remaining_message, parsed_date, parsed_time)

    # 沒有找到日期
    return (remaining_message, None, None)
