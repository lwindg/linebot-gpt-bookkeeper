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
import re
from dataclasses import dataclass, field
from typing import Literal, Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo
from openai import OpenAI

from app.config import OPENAI_API_KEY, GPT_MODEL
from app.prompts import CASHFLOW_INTENTS_PROMPT, MULTI_EXPENSE_PROMPT, UPDATE_INTENT_PROMPT
from app.schemas import MULTI_BOOKKEEPING_SCHEMA
from app.exchange_rate import ExchangeRateService
from app.kv_store import KVStore
from app.category_resolver import resolve_category_autocorrect
from app.payment_resolver import normalize_payment_method, detect_payment_method
from app.project_resolver import infer_project
from app.cashflow_rules import (
    infer_transfer_mode,
    infer_transfer_accounts,
    normalize_cashflow_payment_method,
)

logger = logging.getLogger(__name__)

_CASHFLOW_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("card_payment", ("繳卡費", "信用卡費", "繳信用卡", "刷卡費")),
    ("transfer", ("轉帳", "匯款", "轉入", "轉出")),
    ("withdrawal", ("提款", "領現", "領錢", "ATM")),
    ("income", ("收入", "入帳", "薪水", "退款", "退費", "收款")),
)

_CASHFLOW_CATEGORIES = {
    "withdrawal": "提款",
    "transfer": "轉帳",
    "income": "收入",
    "card_payment": "繳卡費",
}

_UPDATE_KEYWORDS = ("修改", "更改", "改", "更新")
_UPDATE_FIELD_KEYWORDS = (
    "品項",
    "分類",
    "專案",
    "原幣金額",
    "金額",
    "付款方式",
    "明細說明",
    "明細",
    "必要性",
)

_UPDATE_FIELD_PATTERN = re.compile(
    r"(?:修改|更改|改|更新)\s*(?P<field>品項|分類|專案|原幣金額|金額|付款方式|明細說明|明細|必要性)\s*(?:為|成)?\s*(?P<value>.+)$"
)
_UPDATE_FIELD_REVERSED_PATTERN = re.compile(
    r"(?P<field>品項|分類|專案|原幣金額|金額|付款方式|明細說明|明細|必要性)\s*(?:修改|更改|改|更新)\s*(?:為|成)?\s*(?P<value>.+)$"
)

_ADVANCE_OVERRIDE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?P<who>[\u4e00-\u9fff]{1,6})先墊"), "需支付"),
    (re.compile(r"(?P<who>[\u4e00-\u9fff]{1,6})幫我買"), "需支付"),
    (re.compile(r"(?P<who>[\u4e00-\u9fff]{1,6})代訂"), "需支付"),
    (re.compile(r"(?P<who>[\u4e00-\u9fff]{1,6})代付"), "需支付"),
    (re.compile(r"幫(?P<who>[\u4e00-\u9fff]{1,6})代墊"), "代墊"),
    (re.compile(r"幫(?P<who>[\u4e00-\u9fff]{1,6})墊付"), "代墊"),
)

_CASHFLOW_AMOUNT_PATTERN = re.compile(r"-?\d+(?:\.\d+)?")
_SEMANTIC_DATE_TOKENS = ("今天", "昨日", "昨天", "前天", "大前天", "明天", "後天", "大後天")
_EXPLICIT_DATE_PATTERN = re.compile(r"(20\d{2})[/-](\d{1,2})[/-](\d{1,2})")


def _normalize_message_spacing(message: str) -> str:
    text = message or ""
    text = re.sub(r"\$(\d)", r"\1", text)
    text = re.sub(r"(\d)(?=(?:line)(?:轉帳)?)", r"\1 ", text, flags=re.IGNORECASE)
    text = re.sub(r"([\u4e00-\u9fff])([0-9A-Za-z])", r"\1 \2", text)
    text = re.sub(r"([0-9A-Za-z])([\u4e00-\u9fff])", r"\1 \2", text)
    text = re.sub(r"(\d+)\s*(堂|課|次|份|顆|瓶|盒|本|張|包|公斤|kg|g|ml|l|L|個)\b", r"\1\2", text)
    text = re.sub(r"(\d+(?:\.\d+)?)\s*現金", r"\1 元 現金", text)
    return text


def _detect_cashflow_intent(message: str) -> str | None:
    text = message or ""
    for intent_type, keywords in _CASHFLOW_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return intent_type
    return None


def _detect_update_intent(message: str) -> bool:
    text = message or ""
    return any(keyword in text for keyword in _UPDATE_KEYWORDS) and any(
        field in text for field in _UPDATE_FIELD_KEYWORDS
    )


def _detect_advance_override(message: str) -> dict | None:
    text = message or ""
    for pattern, status in _ADVANCE_OVERRIDE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        recipient = (match.group("who") or "").strip()
        if recipient:
            return {"代墊狀態": status, "收款支付對象": recipient}
    return None


def _strip_advance_subject(message: str) -> str:
    text = message or ""
    for pattern, _status in _ADVANCE_OVERRIDE_PATTERNS:
        text = pattern.sub("", text)
    return text.strip()


def _extract_semantic_date_token(message: str) -> Optional[str]:
    text = message or ""
    for token in _SEMANTIC_DATE_TOKENS:
        if token in text:
            return token
    return None


def _extract_first_amount(message: str) -> Optional[float]:
    text = message or ""
    amount_match = _CASHFLOW_AMOUNT_PATTERN.search(text)
    if not amount_match:
        return None
    amount_value = float(amount_match.group(0))
    if amount_value <= 0:
        return None
    return amount_value


def _extract_explicit_date(message: str) -> Optional[str]:
    match = _EXPLICIT_DATE_PATTERN.search(message or "")
    if not match:
        return None
    year, month, day = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    return f"{year:04d}-{month:02d}-{day:02d}"


def _extract_update_fields_simple(message: str) -> Optional[dict]:
    """Try to extract update fields without GPT for simple patterns."""
    text = (message or "").strip()
    if not text:
        return None
    for pattern in (_UPDATE_FIELD_PATTERN, _UPDATE_FIELD_REVERSED_PATTERN):
        match = pattern.search(text)
        if not match:
            continue
        field = match.group("field").strip()
        value = match.group("value").strip()
        if value:
            return {field: value}
    return None


def _normalize_cashflow_category(intent_type: str, raw_category: str) -> str:
    category = (raw_category or "").strip()
    allowed = set(_CASHFLOW_CATEGORIES.values())
    if category in allowed:
        return category
    return _CASHFLOW_CATEGORIES.get(intent_type, category or "收入")


def _fallback_cashflow_items_from_message(message: str, intent_type: str) -> list[dict]:
    text = message or ""
    amount_match = _CASHFLOW_AMOUNT_PATTERN.search(text)
    amount = float(amount_match.group(0)) if amount_match else None
    if not amount or amount <= 0:
        return []

    item_text = text
    if amount_match:
        item_text = item_text.replace(amount_match.group(0), "")
    item_text = re.sub(r"(元|twd|ntd|nt\\$)", "", item_text, flags=re.IGNORECASE).strip()
    item_text = item_text or text.strip()

    payment = normalize_cashflow_payment_method(
        infer_transfer_accounts(text)[0] or ""
    )
    if intent_type == "withdrawal" and payment == "NA":
        payment = "NA"

    return [
        {
            "現金流意圖": intent_type,
            "品項": item_text,
            "原幣金額": amount,
            "原幣別": "TWD",
            "付款方式": payment,
            "分類": _CASHFLOW_CATEGORIES.get(intent_type, ""),
            "日期": None,
        }
    ]


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
    交易類型: Optional[str] = "支出"
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

    intent: Literal["multi_bookkeeping", "cashflow_intents", "conversation", "error", "update_last_entry"]

    # 記帳項目列表（若 intent == "multi_bookkeeping" 則必填）
    entries: List[BookkeepingEntry] = field(default_factory=list)

    # 修改上一筆的欄位（若 intent == "update_last_entry" 則必填）
    fields_to_update: Optional[dict] = None

    # 錯誤訊息（若 intent == "error" 則必填）
    error_message: Optional[str] = None
    error_reason: Optional[str] = None

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
    # 如果已經是 YYYY-MM-DD 格式，直接返回
    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        return date_str

    now = datetime.now(taipei_tz)

    # 處理語義化日期
    semantic_dates = {
        '今天': 0,
        '昨日': -1,
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

    # 處理 YYYY/M/D 或 YYYY/MM/DD 格式
    if re.match(r'^\d{4}/\d{1,2}/\d{1,2}$', date_str):
        parts = date_str.split('/')
        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
        return f"{year:04d}-{month:02d}-{day:02d}"

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
    if result.intent in ("multi_bookkeeping", "cashflow_intents"):
        # 單項目：直接回傳第一個 entry
        if len(result.entries) == 1:
            return result.entries[0]
        # 多項目：回傳第一個 entry（v1 不支援多項目）
        else:
            logger.warning("v1 API called with multi-item message, returning first item only")
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


def process_multi_expense_gpt_only(user_message: str, *, debug: bool = False) -> MultiExpenseResult:
    """
    強制使用 GPT-first 路徑處理訊息（忽略 USE_PARSER_FIRST flag）。
    
    用於 Shadow Mode 驗證，確保可以取得舊路徑結果進行比對。
    
    Args:
        user_message: 使用者訊息文字
        debug: 是否輸出除錯資訊
    
    Returns:
        MultiExpenseResult: GPT-first 處理結果
    """
    return _process_multi_expense_impl(user_message, debug=debug)


def process_multi_expense(user_message: str, *, debug: bool = False) -> MultiExpenseResult:
    """
    處理單一訊息的多項目支出（v1.5.0 新功能）

    流程：
    1. 構建 GPT messages（依關鍵字選擇系統提示）
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
        - cashflow_intents: 現金流意圖（cashflow_items 陣列）
        - update_last_entry: 修改上一筆記帳（fields_to_update 物件）
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
    # === Phase 3: Parser-first mode (feature flag) ===
    from app.config import USE_PARSER_FIRST
    
    if USE_PARSER_FIRST:
        # 檢查是否需要 fallback 到 GPT-first
        # update_last_entry 和 conversation 意圖仍需 GPT 處理
        update_hint = _detect_update_intent(user_message)
        if update_hint:
            logger.debug("Parser-first: fallback to GPT for update intent")
        else:
            # 使用 Parser-first 流程
            from app.processor import process_with_parser
            try:
                result = process_with_parser(user_message)
                if debug:
                    logger.info(f"[parser-first] result.intent={result.intent}, entries={len(result.entries)}")
                # 若 parser-first 成功解析出交易則回傳
                if result.intent in ("multi_bookkeeping", "cashflow_intents") and len(result.entries) > 0:
                    return result
                # 否則 fallback 到 GPT-first（可能是對話意圖）
                logger.debug("Parser-first: no transactions found, fallback to GPT")
            except Exception as e:
                # Parser 失敗 → fallback 到 GPT-first（可能是對話訊息）
                logger.debug(f"Parser-first failed, fallback to GPT: {e}")
    # === End Phase 3 ===
    
    return _process_multi_expense_impl(user_message, debug=debug)


def _process_multi_expense_impl(user_message: str, *, debug: bool = False) -> MultiExpenseResult:
    """GPT-first 實作（內部使用）"""

    try:
        user_message = _normalize_message_spacing(user_message)
        base_message = user_message

        # 初始化 OpenAI client
        client = OpenAI(api_key=OPENAI_API_KEY)

        # 初始化 ExchangeRateService (v003-multi-currency)
        kv_store = KVStore()
        exchange_rate_service = ExchangeRateService(kv_store)

        update_hint = _detect_update_intent(base_message)
        cashflow_hint = _detect_cashflow_intent(base_message) if not update_hint else None
        advance_override = _detect_advance_override(base_message)
        if update_hint:
            system_prompt = UPDATE_INTENT_PROMPT
        else:
            system_prompt = CASHFLOW_INTENTS_PROMPT if cashflow_hint else MULTI_EXPENSE_PROMPT
        if debug:
            prompt_type = "update" if update_hint else ("cashflow" if cashflow_hint else "multi")
            logger.info(
                f"[debug] prompt_type={prompt_type} update_hint={update_hint} cashflow_hint={cashflow_hint} "
                f"advance_override={advance_override}"
            )

        if advance_override:
            stripped_message = _strip_advance_subject(user_message)
            if stripped_message:
                user_message = stripped_message
            parsed_amount = _extract_first_amount(base_message)
            payment_override = detect_payment_method(base_message)
            user_message = (
                f"{user_message}\n"
                f"（已判定代墊狀態:{advance_override['代墊狀態']}；"
                f"收款支付對象:{advance_override['收款支付對象']}；"
                + (f"已解析金額:{parsed_amount}；" if parsed_amount is not None else "")
                + ("已指定付款方式:NA；" if not payment_override else "")
                + "付款方式若未提供請填 NA；"
                "多項目時僅套用最近項目）"
            )
        if debug:
            logger.info(f"[debug] gpt_user_message={user_message}")

        def _run_completion(message_text: str) -> str:
            completion = client.chat.completions.create(
                model=GPT_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message_text},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": MULTI_BOOKKEEPING_SCHEMA,
                },
            )
            return completion.choices[0].message.content

        # 取得回應並解析 JSON（update intent 先嘗試本地抽取）
        data = None
        if update_hint:
            local_fields = _extract_update_fields_simple(base_message)
            if local_fields:
                data = {"intent": "update_last_entry", "fields_to_update": local_fields}
        if data is None:
            response_text = _run_completion(user_message)
            if debug:
                logger.info(f"[debug] gpt_raw_response={response_text}")
            logger.info(f"GPT multi-expense response: {response_text}")
            data = json.loads(response_text)
        intent = data.get("intent")

        if intent == "multi_bookkeeping":
            # 多項目記帳意圖：提取資料並驗證
            payment_method = normalize_payment_method(data.get("payment_method", ""))
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
            explicit_date = _extract_explicit_date(user_message)
            date_str = data.get("date")
            if explicit_date:
                shared_date = explicit_date
            elif date_str:
                try:
                    shared_date = parse_semantic_date(date_str, taipei_tz)
                    logger.info(f"使用提取的日期：{date_str} → {shared_date}")
                except Exception as e:
                    logger.warning(f"日期解析失敗，使用今天：{date_str}, error: {e}")
                    shared_date = now.strftime("%Y-%m-%d")
            else:
                shared_date = now.strftime("%Y-%m-%d")

            # 生成批次ID（作為基礎時間戳）
            first_item = items[0].get("品項") if items else None
            use_current_time = not date_str  # 若未提供日期，使用當前時間
            batch_id = generate_transaction_id(
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

                # 取得幣別（v003-multi-currency）
                原幣別 = item_data.get("原幣別", "TWD")
                匯率 = 1.0

                # 若為外幣，查詢匯率（v003-multi-currency）
                if 原幣別 != "TWD":
                    rate = exchange_rate_service.get_rate(原幣別)
                    if rate is not None:
                        匯率 = rate
                        logger.info(f"Got exchange rate for {原幣別}: {匯率}")
                    else:
                        # 匯率查詢失敗，回傳錯誤
                        logger.error(f"Failed to get exchange rate for {原幣別}")
                        return MultiExpenseResult(
                            intent="error",
                            error_message=f"無法取得 {原幣別} 匯率，請稍後再試或改用新台幣記帳"
                        )

                # 生成獨立的交易ID（批次ID + 序號）
                if len(items) > 1:
                    # 多項目：批次ID-序號（例如：20251125-143027-01）
                    transaction_id = f"{batch_id}-{idx:02d}"
                else:
                    # 單項目：直接使用批次ID
                    transaction_id = batch_id

                # 補充預設值和共用欄位
                分類 = resolve_category_autocorrect(item_data.get("分類", ""))
                project_raw = item_data.get("專案")
                project = project_raw.strip() if isinstance(project_raw, str) else ""
                inferred_project = infer_project(分類)
                if not project:
                    project = inferred_project
                elif project == "日常" and inferred_project != "日常":
                    project = inferred_project

                entry = BookkeepingEntry(
                    intent="bookkeeping",
                    日期=shared_date,
                    品項=品項,
                    原幣別=原幣別,
                    原幣金額=float(原幣金額),
                    匯率=匯率,
                    付款方式=payment_method,
                    交易ID=transaction_id,
                    明細說明=item_data.get("明細說明", ""),
                    分類=分類,
                    交易類型="支出",
                    專案=project,
                    必要性=item_data.get("必要性", "必要日常支出"),
                    代墊狀態=item_data.get("代墊狀態", "無"),
                    收款支付對象=item_data.get("收款支付對象", ""),
                    附註=""
                )

                entries.append(entry)

            result = MultiExpenseResult(
                intent="multi_bookkeeping",
                entries=entries
            )
            return result

        elif intent == "cashflow_intents":
            cashflow_items = data.get("cashflow_items", [])
            if not cashflow_items:
                fallback_intent = _detect_cashflow_intent(user_message)
                cashflow_items = _fallback_cashflow_items_from_message(user_message, fallback_intent) if fallback_intent else []
            return _process_cashflow_items(cashflow_items, user_message)

        elif intent == "update_last_entry":
            # 修改上一筆記帳：提取要更新的欄位
            fields_to_update = data.get("fields_to_update", {})

            if not isinstance(fields_to_update, dict) or not fields_to_update:
                return MultiExpenseResult(
                    intent="error",
                    error_message="缺少欄位名稱或新值，請提供要修改的欄位與內容。"
                )

            if len(fields_to_update) != 1:
                return MultiExpenseResult(
                    intent="error",
                    error_message="一次只允許更新一個欄位，請分開修改。"
                )

            field_name, field_value = next(iter(fields_to_update.items()))
            field_aliases = {
                "金額": "原幣金額",
                "明細": "明細說明",
                "帳戶": "付款方式",
            }
            field_name = field_aliases.get(field_name, field_name)

            allowed_fields = {
                "品項",
                "分類",
                "專案",
                "原幣金額",
                "付款方式",
                "明細說明",
                "必要性",
            }
            if field_name not in allowed_fields:
                return MultiExpenseResult(
                    intent="error",
                    error_message="欄位不支援，請提供可修改的欄位名稱。"
                )

            if field_value in (None, ""):
                return MultiExpenseResult(
                    intent="error",
                    error_message="缺少欄位名稱或新值，請提供要修改的欄位與內容。"
                )

            if field_name == "付款方式":
                field_value = normalize_payment_method(str(field_value))

            if field_name == "分類":
                field_value = resolve_category_autocorrect(str(field_value))

            if field_name == "原幣金額":
                try:
                    amount_value = float(field_value)
                except (TypeError, ValueError):
                    return MultiExpenseResult(
                        intent="error",
                        error_message="缺少欄位名稱或新值，請提供要修改的欄位與內容。"
                    )
                if amount_value < 0:
                    return MultiExpenseResult(
                        intent="error",
                        error_message="金額不可為負數"
                    )
                field_value = amount_value

            return MultiExpenseResult(
                intent="update_last_entry",
                fields_to_update={field_name: field_value}
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
            error_reason = data.get("reason")
            return MultiExpenseResult(
                intent="error",
                error_message=error_msg,
                error_reason=error_reason
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


def _process_cashflow_items(cashflow_items: list[dict], user_message: str) -> MultiExpenseResult:
    if not cashflow_items:
        return MultiExpenseResult(
            intent="error",
            error_message="未識別到任何現金流項目"
        )

    taipei_tz = ZoneInfo('Asia/Taipei')
    now = datetime.now(taipei_tz)

    transfer_mode = infer_transfer_mode(user_message)
    transfer_source, transfer_target = infer_transfer_accounts(user_message)

    entries: list[BookkeepingEntry] = []

    for item_data in cashflow_items:
        intent_type = item_data.get("現金流意圖")
        item_name = item_data.get("品項")
        amount = item_data.get("原幣金額")
        currency = item_data.get("原幣別", "TWD")
        payment_method_raw = item_data.get("付款方式", "")
        category_raw = item_data.get("分類", "")

        if not intent_type or not item_name:
            return MultiExpenseResult(
                intent="error",
                error_message="現金流資料不完整，請補充意圖與品項"
            )

        if amount is None or float(amount) <= 0:
            return MultiExpenseResult(
                intent="error",
                error_message="金額必須為正數"
            )

        payment_method = normalize_cashflow_payment_method(payment_method_raw)
        category = _normalize_cashflow_category(intent_type, category_raw)
        project = infer_project(category)

        date_str = item_data.get("日期")
        if isinstance(date_str, str) and date_str.strip().upper() == "NA":
            date_str = None
        explicit_date = _extract_explicit_date(user_message)
        semantic_token = _extract_semantic_date_token(user_message)
        shared_date = now.strftime("%Y-%m-%d")
        if explicit_date:
            shared_date = explicit_date
        elif semantic_token:
            shared_date = parse_semantic_date(semantic_token, taipei_tz)
        elif date_str:
            try:
                shared_date = parse_semantic_date(date_str, taipei_tz)
            except Exception as e:
                logger.warning(f"Cashflow date parse failed: {date_str}, error: {e}")

        batch_id = generate_transaction_id(shared_date, None, item_name, use_current_time=not date_str)

        def build_entry(tx_type: str, payment_method_value: str, transaction_id: str) -> BookkeepingEntry:
            return BookkeepingEntry(
                intent="bookkeeping",
                日期=shared_date,
                品項=item_name,
                原幣別=currency,
                原幣金額=float(amount),
                匯率=1.0,
                付款方式=payment_method_value,
                交易ID=transaction_id,
                明細說明=item_data.get("明細說明", ""),
                分類=category,
                交易類型=tx_type,
                專案=project,
                必要性="必要日常支出",
                代墊狀態="無",
                收款支付對象="",
                附註=""
            )

        entry_specs: list[tuple[str, str]] = []
        if intent_type == "withdrawal":
            entry_specs = [("提款", payment_method), ("收入", "現金")]
        elif intent_type == "transfer":
            if transfer_mode == "account":
                source = transfer_source or payment_method
                target = transfer_target or "NA"
                entry_specs = [("轉帳", source), ("收入", target)]
            else:
                entry_specs = [("支出", payment_method)]
        elif intent_type == "income":
            entry_specs = [("收入", payment_method)]
        elif intent_type == "card_payment":
            source = transfer_source or payment_method
            target = transfer_target or "信用卡"
            entry_specs = [("轉帳", source), ("收入", target)]
        else:
            return MultiExpenseResult(
                intent="error",
                error_message=f"無法識別現金流意圖：{intent_type}"
            )

        total_entries = len(entry_specs)
        for idx, (tx_type, payment_method_value) in enumerate(entry_specs, start=1):
            transaction_id = batch_id if total_entries == 1 else f"{batch_id}-{idx:02d}"
            entries.append(build_entry(tx_type, payment_method_value, transaction_id))

    return MultiExpenseResult(
        intent="cashflow_intents",
        entries=entries
    )


def process_receipt_data(receipt_items: List, receipt_date: Optional[str] = None) -> MultiExpenseResult:
    """
    將收據資料轉換為記帳項目（v1.5.0 圖片識別，v1.8.1 支援多日期）

    流程：
    1. 接收從 Vision API 提取的收據項目（List[ReceiptItem]，可能包含日期）
    2. 為每個項目補充預設值（日期優先使用項目自帶的日期）
    3. 為每個項目生成獨立交易ID（基於各自的日期）
    4. 回傳 MultiExpenseResult

    Args:
        receipt_items: 從圖片識別出的收據項目列表（ReceiptItem 物件，可能包含日期）
        receipt_date: 收據的整體日期（YYYY-MM-DD），作為 fallback

    Returns:
        MultiExpenseResult: 包含完整記帳資料的結果

    Examples:
        >>> from app.image_handler import ReceiptItem
        >>> items = [
        ...     ReceiptItem(品項="咖啡", 原幣金額=50, 付款方式="現金", 日期="2025-11-15"),
        ...     ReceiptItem(品項="三明治", 原幣金額=80, 付款方式="現金", 日期="2025-11-15")
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

        # 台北時區
        taipei_tz = ZoneInfo('Asia/Taipei')
        now = datetime.now(taipei_tz)
        current_date = now.strftime("%Y-%m-%d")

        # 取得共用付款方式（第一個項目的付款方式）
        # 如果 Vision API 無法識別，預設為「現金」（最常見情況）
        payment_method_raw = receipt_items[0].付款方式 if receipt_items[0].付款方式 else "現金"
        payment_method = normalize_payment_method(payment_method_raw)
        payment_method_is_default = not receipt_items[0].付款方式  # 標記是否使用預設值

        # v1.9.0: 生成批次時間戳（用於識別同一批次的項目）
        # 使用當前時間作為批次識別符
        batch_timestamp = now.strftime("%Y%m%d-%H%M%S")
        logger.info(f"批次時間戳：{batch_timestamp}")

        # 第一步：為每個項目生成基礎交易ID（基於實際日期）
        entries = []
        base_transaction_ids = []  # 儲存基礎交易ID（用於檢測重複）

        for idx, receipt_item in enumerate(receipt_items, start=1):
            # 日期選擇策略（混合模式，三層 fallback）
            # 優先級：項目日期 → 收據整體日期 → 當前日期
            if receipt_item.日期:
                item_date = receipt_item.日期
                logger.info(f"項目 {idx} 使用 Vision API 辨識的日期：{item_date}")
            elif receipt_date:
                item_date = receipt_date
                logger.info(f"項目 {idx} 使用收據整體日期（fallback）：{item_date}")
            else:
                item_date = current_date
                logger.info(f"項目 {idx} 使用當前日期（fallback）：{item_date}")

            # 生成基礎交易ID（使用實際日期）
            base_id = generate_transaction_id(
                item_date,
                None,  # 暫不支援時間提取
                receipt_item.品項,
                use_current_time=False  # 收據識別不使用當前時間
            )

            base_transaction_ids.append(base_id)

        # 第二步：處理重複的交易ID，為重複者加上序號
        transaction_id_counter = {}
        final_transaction_ids = []

        for base_id in base_transaction_ids:
            count = base_transaction_ids.count(base_id)
            if count > 1:
                # 有重複：加上序號
                if base_id not in transaction_id_counter:
                    transaction_id_counter[base_id] = 1
                else:
                    transaction_id_counter[base_id] += 1

                seq = transaction_id_counter[base_id]
                transaction_id = f"{base_id}-{seq:02d}"
            else:
                # 無重複：直接使用
                transaction_id = base_id

            final_transaction_ids.append(transaction_id)

        # 第三步：建立 BookkeepingEntry 物件
        for idx, receipt_item in enumerate(receipt_items, start=1):
            # 取得對應的日期和交易ID
            if receipt_item.日期:
                item_date = receipt_item.日期
            elif receipt_date:
                item_date = receipt_date
            else:
                item_date = current_date

            transaction_id = final_transaction_ids[idx - 1]

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

            # Normalize and enforce allow-list (auto-correct; fallback to 家庭支出)
            分類 = resolve_category_autocorrect(分類, fallback="家庭支出")
            專案 = infer_project(分類)

            entry = BookkeepingEntry(
                intent="bookkeeping",
                日期=item_date,  # 使用項目自己的日期
                品項=品項,
                原幣別="TWD",
                原幣金額=float(receipt_item.原幣金額),
                匯率=1.0,
                付款方式=payment_method,
                交易ID=transaction_id,  # 使用實際日期的交易ID
                明細說明=f"收據識別 {idx}/{len(receipt_items)}",
                分類=分類,
                交易類型="支出",
                專案=專案,
                必要性="必要日常支出",
                代墊狀態="無",
                收款支付對象="",
                附註=""
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
