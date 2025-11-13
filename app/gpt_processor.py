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
from app.mappings import normalize_payment_method

logger = logging.getLogger(__name__)


@dataclass
class BookkeepingEntry:
    """記帳資料結構"""

    intent: Literal["bookkeeping", "conversation"]

    # 記帳欄位（若 intent == "bookkeeping" 則必填）
    日期: Optional[str] = None              # YYYY-MM-DD
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


def generate_transaction_id(date_str: str, time_str: Optional[str] = None, item: Optional[str] = None, is_today: bool = False) -> str:
    """
    生成交易ID：YYYYMMDD-HHMMSS（使用台北時間）

    時間戳記生成規則：
    1. 如果提供明確時間 → 使用該時間
    2. 如果沒有明確時間：
       - 記錄今天的消費（is_today=True）→ 使用當前時間
       - 記錄過去日期的消費（is_today=False）：
         - 品項含「早餐」→ 08:00:00
         - 品項含「午餐」→ 12:00:00
         - 品項含「晚餐」→ 18:00:00
         - 其他 → 23:59:00

    Args:
        date_str: 日期字串（YYYY-MM-DD 格式）
        time_str: 時間字串（HH:MM 或 HH:MM:SS 格式，可選）
        item: 品項名稱（用於推測合理時間，可選）
        is_today: 是否為今天的消費（預設 False）

    Returns:
        str: 交易ID（格式：YYYYMMDD-HHMMSS）

    Examples:
        >>> generate_transaction_id("2025-11-13", None, "午餐", is_today=True)
        '20251113-140530'  # 使用當前時間
        >>> generate_transaction_id("2025-11-12", None, "午餐", is_today=False)
        '20251112-120000'  # 使用推測時間
        >>> generate_transaction_id("2025-11-12", None, "線上英文課", is_today=False)
        '20251112-235900'  # 非三餐，使用 23:59:00
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
    elif is_today:
        # 情況2：記錄今天的消費，使用當前時間
        now = datetime.now(taipei_tz)
        hour, minute, second = now.hour, now.minute, now.second
    elif item:
        # 情況3-5：記錄過去日期的消費，根據品項推測時間
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
            if not entry_data.get("日期"):
                entry_data["日期"] = datetime.now(taipei_tz).strftime("%Y-%m-%d")

            # 提取時間和品項用於生成交易ID
            time_str = entry_data.get("時間")  # GPT可能會返回時間（可選）
            item = entry_data.get("品項")
            date_str = entry_data.get("日期")

            # 判斷是否為今天（用於決定時間戳記邏輯）
            today_str = datetime.now(taipei_tz).strftime("%Y-%m-%d")
            is_today = (date_str == today_str)

            # 生成交易ID（根據日期、時間、品項智能推測時間戳記）
            entry_data["交易ID"] = generate_transaction_id(date_str, time_str, item, is_today)

            # 移除時間欄位（不應發送到webhook）
            if "時間" in entry_data:
                del entry_data["時間"]

            # 🆕 本地化標準化付款方式（後處理，不影響速度）
            if "付款方式" in entry_data:
                entry_data["付款方式"] = normalize_payment_method(entry_data["付款方式"])

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
