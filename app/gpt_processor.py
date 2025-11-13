"""
GPT 處理器模組

此模組負責：
1. 呼叫 OpenAI GPT API 分析使用者訊息
2. 判斷意圖（記帳 vs 一般對話）
3. 結構化記帳資料
4. 生成交易ID
"""

import json
import logging
from dataclasses import dataclass
from typing import Literal, Optional
from datetime import datetime
from zoneinfo import ZoneInfo
from openai import OpenAI

from app.config import OPENAI_API_KEY, GPT_MODEL
from app.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


@dataclass
class BookkeepingEntry:
    """記帳資料結構"""

    intent: Literal["bookkeeping", "conversation"]

    # 記帳欄位（若 intent == "bookkeeping" 則必填）
    日期: Optional[str] = None              # YYYY-MM-DD
    時間: Optional[str] = None              # YYYY-MM-DD
    品項: Optional[str] = None
    原幣別: Optional[str] = "TWD"
    原幣金額: Optional[float] = None
    匯率: Optional[float] = 1.0
    付款方式: Optional[str] = None
    交易ID: Optional[str] = None           # YYYYMMDD-HHMMSS
    明細說明: Optional[str] = ""
    分類: Optional[str] = None
    專案: Optional[str] = "日常"
    必要性: Optional[str] = None
    代墊狀態: Optional[str] = "無"
    收款支付對象: Optional[str] = ""
    附註: Optional[str] = ""

    # 對話欄位（若 intent == "conversation" 則必填）
    response_text: Optional[str] = None


def parse_semantic_date(date_str: str, taipei_tz: ZoneInfo) -> str:
    """
    解析語義化日期或標準日期格式

    支援格式：
    - 語義化：「今天」、「昨天」、「前天」、「明天」、「後天」
    - MM-DD 格式：「11-12」→「2025-11-12」
    - YYYY-MM-DD 格式：「2025-11-12」（不轉換）

    Args:
        date_str: 日期字串
        taipei_tz: 台北時區

    Returns:
        str: YYYY-MM-DD 格式的日期

    Examples:
        >>> tz = ZoneInfo('Asia/Taipei')
        >>> parse_semantic_date("今天", tz)
        '2025-11-13'
        >>> parse_semantic_date("昨天", tz)
        '2025-11-12'
        >>> parse_semantic_date("11-12", tz)
        '2025-11-12'
        >>> parse_semantic_date("2025-11-12", tz)
        '2025-11-12'
    """
    from datetime import timedelta
    import re

    # 如果已經是 YYYY-MM-DD 格式，直接返回
    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        return date_str

    now = datetime.now(taipei_tz)

    # 處理語義化日期
    semantic_dates = {
        '今天': 0,
        '昨天': -1,
        '前天': -2,
        '大前天': -3,
        '明天': 1,
        '後天': 2,
        '大後天': 3,
    }

    if date_str in semantic_dates:
        target_date = now + timedelta(days=semantic_dates[date_str])
        return target_date.strftime("%Y-%m-%d")

    # 處理 MM-DD 格式（補上當前年份）
    if re.match(r'^\d{1,2}-\d{1,2}$', date_str):
        parts = date_str.split('-')
        month, day = int(parts[0]), int(parts[1])
        return f"{now.year:04d}-{month:02d}-{day:02d}"

    # 處理 M/D 或 MM/DD 格式
    if re.match(r'^\d{1,2}/\d{1,2}$', date_str):
        parts = date_str.split('/')
        month, day = int(parts[0]), int(parts[1])
        return f"{now.year:04d}-{month:02d}-{day:02d}"

    # 其他情況，返回今天
    logger.warning(f"Unknown date format: {date_str}, using today")
    return now.strftime("%Y-%m-%d")


def generate_transaction_id(date_str: str, time_str: Optional[str] = None, item: Optional[str] = None, use_current_time: bool = False) -> str:
    """
    生成交易ID：YYYYMMDD-HHMMSS（使用台北時間）

    時間戳記生成規則：
    1. 如果提供明確時間 → 使用該時間
    2. 如果用戶未提供日期（預設今天）且無明確時間 → 使用當前時間
    3. 如果提供過去日期且無明確時間，根據品項推測：
       - 品項含「早餐」→ 08:00:00
       - 品項含「午餐」→ 12:00:00
       - 品項含「晚餐」→ 18:00:00
       - 其他情況 → 23:59:00

    Args:
        date_str: 日期字串（YYYY-MM-DD 格式）
        time_str: 時間字串（HH:MM 或 HH:MM:SS 格式，可選）
        item: 品項名稱（用於推測合理時間，可選）
        use_current_time: 是否使用當前時間（當用戶未提供日期時為 True）

    Returns:
        str: 交易ID（格式：YYYYMMDD-HHMMSS）

    Examples:
        >>> generate_transaction_id("2025-11-13", None, "點心", use_current_time=True)
        '20251113-143027'  # 使用當前時間
        >>> generate_transaction_id("2025-11-12", "14:30", None)
        '20251112-143000'
        >>> generate_transaction_id("2025-11-12", None, "午餐")
        '20251112-120000'
        >>> generate_transaction_id("2025-11-12", None, "線上英文課")
        '20251112-235900'
    """
    taipei_tz = ZoneInfo('Asia/Taipei')

    # 解析日期
    date_parts = date_str.split('-')
    year, month, day = int(date_parts[0]), int(date_parts[1]), int(date_parts[2])

    # 決定時間
    if time_str:
        # 情況1：有明確時間
        time_parts = time_str.split(':')
        if len(time_parts) == 2:
            hour, minute, second = int(time_parts[0]), int(time_parts[1]), 0
        else:  # len == 3
            hour, minute, second = int(time_parts[0]), int(time_parts[1]), int(time_parts[2])
    elif use_current_time:
        # 情況2：用戶未提供日期（預設今天）且無明確時間，使用當前時間
        now = datetime.now(taipei_tz)
        hour, minute, second = now.hour, now.minute, now.second
    elif item:
        # 情況3-5：提供過去日期且無明確時間，根據品項推測時間
        if '早餐' in item:
            hour, minute, second = 8, 0, 0
        elif '午餐' in item:
            hour, minute, second = 12, 0, 0
        elif '晚餐' in item:
            hour, minute, second = 18, 0, 0
        else:
            # 其他品項，使用 23:59:00
            hour, minute, second = 23, 59, 0
    else:
        # 無時間、無品項：使用 23:59:00
        hour, minute, second = 23, 59, 0

    # 組合日期時間並格式化
    dt = datetime(year, month, day, hour, minute, second, tzinfo=taipei_tz)
    return dt.strftime("%Y%m%d-%H%M%S")


def process_message(user_message: str) -> BookkeepingEntry:
    """
    處理使用者訊息並回傳結構化結果

    流程：
    1. 構建 GPT messages（system + user）
    2. 呼叫 OpenAI API
    3. 解析回應（判斷 intent）
    4. 若為記帳 → 驗證必要欄位、生成交易ID、補充預設值
    5. 回傳 BookkeepingEntry

    Args:
        user_message: 使用者訊息文字

    Returns:
        BookkeepingEntry: 處理後的結果

    Raises:
        Exception: OpenAI API 呼叫失敗
        ValueError: JSON 解析失敗或必要欄位缺失
    """
    try:
        # 初始化 OpenAI client
        client = OpenAI(api_key=OPENAI_API_KEY)

        # 呼叫 Chat Completions API
        completion = client.chat.completions.create(
            model=GPT_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ],
            response_format={"type": "json_object"}  # 確保 JSON 輸出
        )

        # 取得回應並解析 JSON
        response_text = completion.choices[0].message.content
        logger.info(f"GPT response: {response_text}")

        data = json.loads(response_text)
        intent = data.get("intent")

        if intent == "bookkeeping":
            # 記帳意圖：提取資料並驗證
            entry_data = data.get("data", {})

            # 驗證必要欄位
            required_fields = ["品項", "原幣金額", "付款方式"]
            for field in required_fields:
                if not entry_data.get(field):
                    raise ValueError(f"Missing required field: {field}")

            # 補充日期預設值（在生成交易ID之前）
            taipei_tz = ZoneInfo('Asia/Taipei')

            # 處理日期（包括語義化日期轉換）
            date_value = entry_data.get("日期")
            user_provided_date = bool(date_value)  # 記錄用戶是否提供日期

            if date_value:
                # 處理語義化日期和標準日期格式
                date_str = parse_semantic_date(date_value, taipei_tz)
                entry_data["日期"] = date_str
            else:
                # 無日期，使用今天
                entry_data["日期"] = datetime.now(taipei_tz).strftime("%Y-%m-%d")

            # 提取時間和品項用於生成交易ID
            time_str = entry_data.get("時間")  # GPT可能會返回時間（可選）
            item = entry_data.get("品項")
            date_str = entry_data.get("日期")

            # 判斷是否為今天且無明確時間（用戶沒提供日期，應使用當前時間）
            use_current_time = not user_provided_date and not time_str

            # 生成交易ID（根據日期、時間、品項智能推測時間戳記）
            entry_data["交易ID"] = generate_transaction_id(date_str, time_str, item, use_current_time)

            # 移除時間欄位（不應發送到webhook）
            if "時間" in entry_data:
                del entry_data["時間"]

            # 確保數值型別正確
            if "原幣金額" in entry_data:
                entry_data["原幣金額"] = float(entry_data["原幣金額"])
            if "匯率" in entry_data:
                entry_data["匯率"] = float(entry_data["匯率"])
            else:
                entry_data["匯率"] = 1.0

            # 確保必要欄位有預設值
            entry_data.setdefault("原幣別", "TWD")
            entry_data.setdefault("專案", "日常")
            entry_data.setdefault("代墊狀態", "無")
            entry_data.setdefault("明細說明", "")
            entry_data.setdefault("收款支付對象", "")
            entry_data.setdefault("附註", "")

            return BookkeepingEntry(intent="bookkeeping", **entry_data)

        elif intent == "conversation":
            # 一般對話：提取回應文字
            response = data.get("response", "")
            return BookkeepingEntry(
                intent="conversation",
                response_text=response
            )

        else:
            raise ValueError(f"Unknown intent: {intent}")

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse GPT JSON response: {e}")
        raise ValueError(f"Invalid JSON response from GPT: {e}")

    except Exception as e:
        logger.error(f"GPT API error: {e}")
        raise
