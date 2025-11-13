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


def generate_transaction_id() -> str:
    """
    生成交易ID：YYYYMMDD-HHMMSS

    格式範例：20251112-143025（2025-11-12 14:30:25）

    Returns:
        str: 交易ID
    """
    now = datetime.now()
    return now.strftime("%Y%m%d-%H%M%S")


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

            # 生成交易ID
            entry_data["交易ID"] = generate_transaction_id()

            # 補充預設值
            if not entry_data.get("日期"):
                entry_data["日期"] = datetime.now().strftime("%Y-%m-%d")

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
