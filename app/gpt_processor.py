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
from dataclasses import dataclass, field
from typing import Literal, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo
from openai import OpenAI

from app.config import OPENAI_API_KEY, GPT_MODEL
from app.prompts import MULTI_EXPENSE_PROMPT

logger = logging.getLogger(__name__)


@dataclass
class BookkeepingEntry:
    """記帳資料結構"""

    intent: Literal["bookkeeping", "conversation"]

    # 記帳欄位（若 intent == "bookkeeping" 則必填）
    日期: Optional[str] = None              # YYYY-MM-DD
    時間: Optional[str] = None              # HH:MM
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


@dataclass
class MultiExpenseResult:
    """多項目支出處理結果（v1.5.0 新增）"""

    intent: Literal["multi_bookkeeping", "conversation", "error", "update_last_entry"]

    # 記帳項目列表（若 intent == "multi_bookkeeping" 則必填）
    entries: List[BookkeepingEntry] = field(default_factory=list)

    # 修改上一筆的欄位（若 intent == "update_last_entry" 則必填）
    fields_to_update: Optional[dict] = None

    # 錯誤訊息（若 intent == "error" 則必填）
    error_message: Optional[str] = None

    # 對話回應（若 intent == "conversation" 則必填）
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
    處理使用者訊息並回傳結構化結果（v1 向後相容接口）

    **注意**：此函式內部調用 process_multi_expense，已統一使用 v1.5.0 prompt。
    單項目記帳會自動轉換為 v1 格式回傳。

    Args:
        user_message: 使用者訊息文字

    Returns:
        BookkeepingEntry: 處理後的結果（v1 格式）

    Raises:
        Exception: 處理失敗
    """
    # 內部調用 v1.5.0 處理函式
    result = process_multi_expense(user_message)

    # 轉換回 v1 格式
    if result.intent == "multi_bookkeeping":
        # 單項目：直接回傳第一個 entry
        if len(result.entries) == 1:
            return result.entries[0]
        # 多項目：回傳第一個 entry（v1 不支援多項目）
        else:
            logger.warning(f"v1 API called with multi-item message, returning first item only")
            return result.entries[0]

    elif result.intent == "conversation":
        # 對話意圖：轉換為 v1 格式
        return BookkeepingEntry(
            intent="conversation",
            response_text=result.response_text
        )

    elif result.intent == "error":
        # 錯誤意圖：轉換為對話回應
        return BookkeepingEntry(
            intent="conversation",
            response_text=result.error_message
        )

    else:
        raise ValueError(f"Unknown intent from process_multi_expense: {result.intent}")


def process_multi_expense(user_message: str) -> MultiExpenseResult:
    """
    處理單一訊息的多項目支出（v1.5.0 新功能）

    流程：
    1. 構建 GPT messages（使用 MULTI_EXPENSE_PROMPT）
    2. 呼叫 OpenAI API
    3. 解析回應（判斷 intent）
    4. 若為多項記帳 → 驗證所有項目、生成共用交易ID、補充預設值
    5. 回傳 MultiExpenseResult

    Args:
        user_message: 使用者訊息文字

    Returns:
        MultiExpenseResult: 處理後的結果

    支援的 intent：
        - multi_bookkeeping: 多項目或單項目記帳（items 陣列）
        - conversation: 一般對話
        - error: 資訊不完整或包含多種付款方式

    Examples:
        >>> result = process_multi_expense("早餐80元，午餐150元，現金")
        >>> result.intent
        'multi_bookkeeping'
        >>> len(result.entries)
        2
        >>> result.entries[0].付款方式
        '現金'
        >>> result.entries[1].付款方式
        '現金'
    """
    try:
        # 初始化 OpenAI client
        client = OpenAI(api_key=OPENAI_API_KEY)

        # 呼叫 Chat Completions API（使用 MULTI_EXPENSE_PROMPT）
        completion = client.chat.completions.create(
            model=GPT_MODEL,
            messages=[
                {"role": "system", "content": MULTI_EXPENSE_PROMPT},
                {"role": "user", "content": user_message}
            ],
            response_format={"type": "json_object"}  # 確保 JSON 輸出
        )

        # 取得回應並解析 JSON
        response_text = completion.choices[0].message.content
        logger.info(f"GPT multi-expense response: {response_text}")

        data = json.loads(response_text)
        intent = data.get("intent")

        if intent == "multi_bookkeeping":
            # 多項目記帳意圖：提取資料並驗證
            payment_method = data.get("payment_method")
            items = data.get("items", [])

            # 驗證必要欄位
            if not payment_method:
                return MultiExpenseResult(
                    intent="error",
                    error_message="缺少付款方式，請提供完整資訊"
                )

            if not items:
                return MultiExpenseResult(
                    intent="error",
                    error_message="未識別到任何記帳項目"
                )

            # 生成共用交易ID（時間戳記格式）
            taipei_tz = ZoneInfo('Asia/Taipei')
            now = datetime.now(taipei_tz)

            # 補充共用日期：優先使用 GPT 提取的日期，否則使用今天
            date_str = data.get("date")
            if date_str:
                try:
                    shared_date = parse_semantic_date(date_str, taipei_tz)
                    logger.info(f"使用提取的日期：{date_str} → {shared_date}")
                except Exception as e:
                    logger.warning(f"日期解析失敗，使用今天：{date_str}, error: {e}")
                    shared_date = now.strftime("%Y-%m-%d")
            else:
                shared_date = now.strftime("%Y-%m-%d")

            # 生成共用交易ID（使用 generate_transaction_id 支援日期和品項）
            first_item = items[0].get("品項") if items else None
            use_current_time = not date_str  # 若未提供日期，使用當前時間
            shared_transaction_id = generate_transaction_id(
                shared_date,
                None,  # 暫不支援時間提取
                first_item,
                use_current_time
            )

            # 處理每個項目
            entries = []
            for idx, item_data in enumerate(items, start=1):
                # 驗證必要欄位
                品項 = item_data.get("品項")
                原幣金額 = item_data.get("原幣金額")

                if not 品項:
                    return MultiExpenseResult(
                        intent="error",
                        error_message=f"第{idx}個項目缺少品項名稱，請提供完整資訊"
                    )

                if 原幣金額 is None:
                    return MultiExpenseResult(
                        intent="error",
                        error_message=f"第{idx}個項目缺少金額，請提供完整資訊"
                    )

                # 補充預設值和共用欄位
                entry = BookkeepingEntry(
                    intent="bookkeeping",
                    日期=shared_date,
                    品項=品項,
                    原幣別="TWD",
                    原幣金額=float(原幣金額),
                    匯率=1.0,
                    付款方式=payment_method,
                    交易ID=shared_transaction_id,
                    明細說明=item_data.get("明細說明", ""),
                    分類=item_data.get("分類", ""),
                    專案="日常",
                    必要性=item_data.get("必要性", "必要日常支出"),
                    代墊狀態=item_data.get("代墊狀態", "無"),
                    收款支付對象=item_data.get("收款支付對象", ""),
                    附註=f"多項目支出 {idx}/{len(items)}" if len(items) > 1 else ""
                )

                entries.append(entry)

            return MultiExpenseResult(
                intent="multi_bookkeeping",
                entries=entries
            )

        elif intent == "update_last_entry":
            # 修改上一筆記帳：提取要更新的欄位
            fields_to_update = data.get("fields_to_update", {})

            if not fields_to_update:
                return MultiExpenseResult(
                    intent="error",
                    error_message="未識別到要更新的欄位"
                )

            return MultiExpenseResult(
                intent="update_last_entry",
                fields_to_update=fields_to_update
            )

        elif intent == "conversation":
            # 一般對話：提取回應文字
            response = data.get("response", "")
            return MultiExpenseResult(
                intent="conversation",
                response_text=response
            )

        elif intent == "error":
            # 錯誤：提取錯誤訊息
            error_msg = data.get("message", "無法處理您的訊息，請檢查輸入格式")
            return MultiExpenseResult(
                intent="error",
                error_message=error_msg
            )

        else:
            # 未知意圖
            return MultiExpenseResult(
                intent="error",
                error_message=f"無法識別意圖：{intent}"
            )

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse GPT JSON response: {e}")
        return MultiExpenseResult(
            intent="error",
            error_message="系統處理訊息時發生錯誤，請重試"
        )

    except Exception as e:
        logger.error(f"GPT API error in process_multi_expense: {e}")
        return MultiExpenseResult(
            intent="error",
            error_message="系統處理訊息時發生錯誤，請重試"
        )


def process_receipt_data(receipt_items: List, receipt_date: Optional[str] = None) -> MultiExpenseResult:
    """
    將收據資料轉換為記帳項目（v1.5.0 圖片識別）

    流程：
    1. 接收從 Vision API 提取的收據項目（List[ReceiptItem]）
    2. 為每個項目補充預設值
    3. 生成共用交易ID（時間戳記格式）
    4. 回傳 MultiExpenseResult

    Args:
        receipt_items: 從圖片識別出的收據項目列表（ReceiptItem 物件）
        receipt_date: 收據上的日期（YYYY-MM-DD），若無則使用當前日期

    Returns:
        MultiExpenseResult: 包含完整記帳資料的結果

    Examples:
        >>> from app.image_handler import ReceiptItem
        >>> items = [
        ...     ReceiptItem(品項="咖啡", 原幣金額=50, 付款方式="現金"),
        ...     ReceiptItem(品項="三明治", 原幣金額=80, 付款方式="現金")
        ... ]
        >>> result = process_receipt_data(items)
        >>> result.intent
        'multi_bookkeeping'
        >>> len(result.entries)
        2
    """
    try:
        if not receipt_items:
            return MultiExpenseResult(
                intent="error",
                error_message="未識別到任何收據項目"
            )

        # 生成共用交易ID（時間戳記格式）
        taipei_tz = ZoneInfo('Asia/Taipei')
        now = datetime.now(taipei_tz)
        shared_transaction_id = now.strftime("%Y%m%d-%H%M%S")

        # 使用收據日期或當前日期
        if receipt_date:
            shared_date = receipt_date
        else:
            shared_date = now.strftime("%Y-%m-%d")

        # 取得共用付款方式（第一個項目的付款方式）
        # 如果 Vision API 無法識別，預設為「現金」（最常見情況）
        payment_method = receipt_items[0].付款方式 if receipt_items[0].付款方式 else "現金"
        payment_method_is_default = not receipt_items[0].付款方式  # 標記是否使用預設值

        # 處理每個項目
        entries = []
        for idx, receipt_item in enumerate(receipt_items, start=1):
            # 分類處理：優先使用 Vision API 提供的分類，沒有則用 GPT 推斷
            品項 = receipt_item.品項
            if receipt_item.分類:
                # Vision API 已提供分類
                分類 = receipt_item.分類
                logger.info(f"使用 Vision API 分類：{品項} → {分類}")
            else:
                # Vision API 未提供分類，使用 GPT 推斷
                分類 = _infer_category(品項)
                logger.info(f"使用 GPT 推斷分類：{品項} → {分類}")

            # 補充預設值和共用欄位
            # 如果付款方式是預設值，在附註中標記
            附註_內容 = f"收據圖片識別 {idx}/{len(receipt_items)}"
            if payment_method_is_default:
                附註_內容 += "；付款方式預設為現金"

            entry = BookkeepingEntry(
                intent="bookkeeping",
                日期=shared_date,
                品項=品項,
                原幣別="TWD",
                原幣金額=float(receipt_item.原幣金額),
                匯率=1.0,
                付款方式=payment_method,
                交易ID=shared_transaction_id,
                明細說明=f"收據識別 {idx}/{len(receipt_items)}",
                分類=分類,
                專案="日常",
                必要性="必要日常支出",
                代墊狀態="無",
                收款支付對象="",
                附註=附註_內容
            )

            entries.append(entry)

        result = MultiExpenseResult(
            intent="multi_bookkeeping",
            entries=entries
        )

        # 如果付款方式是預設值，在 response_text 中加入提醒
        if payment_method_is_default:
            result.response_text = "⚠️ 未從收據識別到付款方式，已預設為「現金」"

        return result

    except Exception as e:
        logger.error(f"處理收據資料時發生錯誤: {e}")
        return MultiExpenseResult(
            intent="error",
            error_message="處理收據資料時發生錯誤，請重試"
        )


def _infer_category(品項: str) -> str:
    """
    使用 GPT 進行智能分類推斷

    Args:
        品項: 品項名稱

    Returns:
        str: 推斷的分類

    Note:
        使用 GPT 根據品項名稱和完整的分類規則進行智能判斷。
        確保分類符合 CLASSIFICATION_RULES 定義的標準。
    """
    from app.prompts import CLASSIFICATION_RULES

    try:
        client = OpenAI(api_key=OPENAI_API_KEY)

        # 簡化的分類 prompt
        classification_prompt = f"""請根據品項名稱判斷最合適的分類。

{CLASSIFICATION_RULES}

**任務**：
- 品項：「{品項}」
- 請從上述分類列表中選擇**最合適**的分類
- 必須使用「大類／子類」或「大類／子類／細類」格式
- 只能使用已定義的分類，不可自創

**輸出格式**：
只回傳分類名稱，不要有其他文字。

範例：
- 輸入：咖啡 → 輸出：家庭／飲品
- 輸入：面紙 → 輸出：家庭／用品／雜項
- 輸入：早餐 → 輸出：家庭／餐飲／早餐
- 輸入：火車票 → 輸出：交通／接駁
"""

        response = client.chat.completions.create(
            model=GPT_MODEL,
            messages=[
                {"role": "user", "content": classification_prompt}
            ],
            max_tokens=50,
            temperature=0.3  # 較低的 temperature 確保穩定輸出
        )

        分類 = response.choices[0].message.content.strip()
        logger.info(f"GPT 分類推斷：{品項} → {分類}")

        return 分類

    except Exception as e:
        logger.error(f"GPT 分類推斷失敗：{e}")
        # 失敗時回退到簡單關鍵字匹配
        return _simple_category_fallback(品項)


def _simple_category_fallback(品項: str) -> str:
    """
    簡單的分類推斷（作為 GPT 分類失敗時的備選方案）

    Args:
        品項: 品項名稱

    Returns:
        str: 推斷的分類
    """
    品項_lower = 品項.lower()

    # 餐飲類別
    if any(keyword in 品項_lower for keyword in ["早餐", "三明治", "蛋餅", "豆漿", "漢堡"]):
        return "家庭／餐飲／早餐"
    elif any(keyword in 品項_lower for keyword in ["午餐", "便當", "麵", "飯"]):
        return "家庭／餐飲／午餐"
    elif any(keyword in 品項_lower for keyword in ["晚餐", "火鍋"]):
        return "家庭／餐飲／晚餐"
    elif any(keyword in 品項_lower for keyword in ["咖啡", "茶", "飲料", "果汁", "冰沙", "奶茶"]):
        return "家庭／飲品"
    elif any(keyword in 品項_lower for keyword in ["點心", "蛋糕", "甜點", "餅乾", "糖果", "巧克力"]):
        return "家庭／點心"

    # 家庭用品
    elif any(keyword in 品項_lower for keyword in ["面紙", "衛生紙", "紙巾", "棉條", "衛生棉"]):
        return "家庭／用品／雜項"

    # 交通類別
    elif any(keyword in 品項_lower for keyword in ["計程車", "uber", "高鐵", "火車", "捷運", "公車"]):
        return "交通／接駁"
    elif any(keyword in 品項_lower for keyword in ["加油", "汽油", "柴油"]):
        return "交通／加油"

    # 預設分類
    else:
        return "家庭支出"
