# -*- coding: utf-8 -*-
"""
Transaction ID generation helpers.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo


_MEAL_TIME_HINTS = {
    "早餐": (7, 0, 0),
    "午餐": (12, 0, 0),
    "晚餐": (18, 0, 0),
}


def generate_transaction_id(
    date_str: str,
    time_str: Optional[str] = None,
    item: Optional[str] = None,
    use_current_time: bool = False,
) -> str:
    """
    生成交易ID：YYYYMMDD-HHMMSS（使用台北時間）

    規則：
    1. 如果提供明確時間 → 使用該時間
    2. 如果用戶未提供日期（預設今天）且無明確時間 → 使用當前時間
    3. 如果提供過去日期且無明確時間，根據品項推測時間：
       - 早餐：07:00
       - 午餐：12:00
       - 晚餐：18:00
       - 其他：23:59
    """
    taipei_tz = ZoneInfo("Asia/Taipei")

    if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        # Fallback to today if format is unexpected
        date_str = datetime.now(taipei_tz).strftime("%Y-%m-%d")

    date_parts = date_str.split('-')
    year, month, day = int(date_parts[0]), int(date_parts[1]), int(date_parts[2])

    # Determine time
    if time_str:
        time_parts = time_str.split(':')
        if len(time_parts) == 2:
            hour, minute, second = int(time_parts[0]), int(time_parts[1]), 0
        else:
            hour, minute, second = int(time_parts[0]), int(time_parts[1]), int(time_parts[2])
    elif use_current_time:
        now = datetime.now(taipei_tz)
        hour, minute, second = now.hour, now.minute, now.second
    else:
        hour, minute, second = 23, 59, 0
        if item:
            for token, (h, m, s) in _MEAL_TIME_HINTS.items():
                if token in item:
                    hour, minute, second = h, m, s
                    break

    dt = datetime(year, month, day, hour, minute, second, tzinfo=taipei_tz)
    return dt.strftime("%Y%m%d-%H%M%S")
