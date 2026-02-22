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
from typing import Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo
from openai import OpenAI

from app.config import OPENAI_API_KEY, GPT_MODEL
from app.gpt.prompts import CASHFLOW_INTENTS_PROMPT, MULTI_EXPENSE_PROMPT, UPDATE_INTENT_PROMPT
from app.schemas import MULTI_BOOKKEEPING_SCHEMA
from app.pipeline.normalize import build_batch_id, assign_transaction_ids
from app.pipeline.transaction_id import generate_transaction_id as _generate_transaction_id
from app.gpt.types import BookkeepingEntry, MultiExpenseResult
from app.gpt.cashflow import (
    detect_cashflow_intent,
    extract_explicit_date,
    fallback_cashflow_items_from_message,
    parse_semantic_date,
    process_cashflow_items,
)
from app.gpt.receipt import process_receipt_data
from app.gpt.update import (
    detect_update_intent,
    extract_update_fields_simple,
    count_update_fields,
)
from app.services.exchange_rate import ExchangeRateService
from app.services.kv_store import KVStore
from app.shared.category_resolver import resolve_category_autocorrect
from app.shared.payment_resolver import normalize_payment_method, detect_payment_method
from app.shared.project_resolver import infer_project
from app.services.lock_service import LockService

logger = logging.getLogger(__name__)

_ADVANCE_OVERRIDE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?P<who>[\u4e00-\u9fff]{1,6})先墊"), "需支付"),
    (re.compile(r"(?P<who>[\u4e00-\u9fff]{1,6})幫我買"), "需支付"),
    (re.compile(r"(?P<who>[\u4e00-\u9fff]{1,6})代訂"), "需支付"),
    (re.compile(r"(?P<who>[\u4e00-\u9fff]{1,6})代付"), "需支付"),
    (re.compile(r"幫(?P<who>[\u4e00-\u9fff]{1,6})代墊"), "代墊"),
    (re.compile(r"幫(?P<who>[\u4e00-\u9fff]{1,6})墊付"), "代墊"),
)

_CASHFLOW_AMOUNT_PATTERN = re.compile(r"-?\d+(?:\.\d+)?")


def _normalize_message_spacing(message: str) -> str:
    text = message or ""
    text = re.sub(r"\$(\d)", r"\1", text)
    text = re.sub(r"(\d)(?=(?:line)(?:轉帳)?)", r"\1 ", text, flags=re.IGNORECASE)
    text = re.sub(r"([\u4e00-\u9fff])([0-9A-Za-z])", r"\1 \2", text)
    text = re.sub(r"([0-9A-Za-z])([\u4e00-\u9fff])", r"\1 \2", text)
    text = re.sub(r"(\d+)\s*(堂|課|次|份|顆|瓶|盒|本|張|包|公斤|kg|g|ml|l|L|個)\b", r"\1\2", text)
    text = re.sub(r"(\d+(?:\.\d+)?)\s*現金", r"\1 元 現金", text)
    return text


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


def _extract_first_amount(message: str) -> Optional[float]:
    text = message or ""
    amount_match = _CASHFLOW_AMOUNT_PATTERN.search(text)
    if not amount_match:
        return None
    amount_value = float(amount_match.group(0))
    if amount_value <= 0:
        return None
    return amount_value




def generate_transaction_id(
    date_str: str,
    time_str: Optional[str] = None,
    item: Optional[str] = None,
    use_current_time: bool = False,
) -> str:
    """Backward-compatible proxy to shared transaction id generator."""
    return _generate_transaction_id(date_str, time_str, item, use_current_time)


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


def process_multi_expense_gpt_only(user_message: str, *, debug: bool = False, user_id: Optional[str] = None) -> MultiExpenseResult:
    """
    強制使用 GPT-first 路徑處理訊息（忽略 USE_PARSER_FIRST flag）。
    
    用於 Shadow Mode 驗證，確保可以取得舊路徑結果進行比對。
    
    Args:
        user_message: 使用者訊息文字
        debug: 是否輸出除錯資訊
        user_id: 使用者 ID (用於讀取鎖定設定)
    
    Returns:
        MultiExpenseResult: GPT-first 處理結果
    """
    return _process_multi_expense_impl(user_message, debug=debug, user_id=user_id)


def process_multi_expense(user_message: str, *, debug: bool = False, user_id: Optional[str] = None) -> MultiExpenseResult:
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
        debug: 是否輸出除錯資訊
        user_id: 使用者 ID (用於讀取鎖定設定)

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
        update_hint = detect_update_intent(user_message)
        if update_hint:
            logger.debug("Parser-first: fallback to GPT for update intent")
        else:
            # 使用 Parser-first 流程
            from app.processor import process_with_parser
            try:
                result = process_with_parser(user_message, user_id=user_id)
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
    
    return _process_multi_expense_impl(user_message, debug=debug, user_id=user_id)


def _process_multi_expense_impl(user_message: str, *, debug: bool = False, user_id: Optional[str] = None) -> MultiExpenseResult:
    """GPT-first 實作（內部使用）"""

    try:
        user_message = _normalize_message_spacing(user_message)
        base_message = user_message

        update_hint = detect_update_intent(base_message)
        cashflow_hint = detect_cashflow_intent(base_message) if not update_hint else None
        if cashflow_hint:
            fallback_items = fallback_cashflow_items_from_message(base_message, cashflow_hint)
            if fallback_items:
                return process_cashflow_items(fallback_items, base_message, user_id=user_id)

        # 初始化 OpenAI client
        client = OpenAI(api_key=OPENAI_API_KEY)

        # 初始化 ExchangeRateService (v003-multi-currency)
        kv_store = KVStore()
        exchange_rate_service = ExchangeRateService(kv_store)
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
            local_fields = extract_update_fields_simple(base_message)
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
            explicit_date = extract_explicit_date(user_message)
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
            batch_id = build_batch_id(
                shared_date,
                item=first_item,
                use_current_time=use_current_time,
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

                # 先填批次ID，最後統一補序號
                transaction_id = batch_id

                # 補充預設值和共用欄位
                分類 = resolve_category_autocorrect(
                    item_data.get("分類", ""),
                    context_text=base_message,
                )
                project_raw = item_data.get("專案")
                project = project_raw.strip() if isinstance(project_raw, str) else ""
                inferred_project = infer_project(分類)
                if not project:
                    project = inferred_project
                elif project == "日常" and inferred_project != "日常":
                    project = inferred_project

                # --- Session Lock logic (v2.2.0) ---
                final_payment = payment_method
                final_currency = 原幣別
                final_fx_rate = 匯率

                if user_id:
                    lock_service = LockService(user_id)
                    
                    # 1. Project Lock
                    if project in ("日常", ""):
                        p_lock = lock_service.get_project_lock()
                        if p_lock:
                            project = p_lock
                    
                    # 2. Payment Lock
                    if final_payment in ("N/A", "") and not cashflow_hint:
                        pay_lock = lock_service.get_payment_lock()
                        if pay_lock:
                            final_payment = pay_lock

                    # 3. Currency Lock (v2.4.0)
                    if final_currency in ("TWD", "") and not cashflow_hint:
                        curr_lock = lock_service.get_currency_lock()
                        if curr_lock and curr_lock != "TWD":
                            final_currency = curr_lock
                            # Update exchange rate for the locked currency
                            rate = exchange_rate_service.get_rate(final_currency)
                            if rate:
                                final_fx_rate = rate

                entry = BookkeepingEntry(
                    intent="bookkeeping",
                    日期=shared_date,
                    品項=品項,
                    原幣別=final_currency,
                    原幣金額=float(原幣金額),
                    匯率=final_fx_rate,
                    付款方式=final_payment,
                    交易ID=transaction_id,
                    明細說明=item_data.get("明細說明", ""),
                    分類=分類,
                    交易類型="支出",
                    專案=project,
                    必要性=__import__("app.shared.necessity_resolver", fromlist=["normalize_necessity"]).normalize_necessity(
                        item_data.get("必要性"),
                        tx_type="支出",
                        is_cashflow=bool(cashflow_hint),
                    ),
                    代墊狀態=item_data.get("代墊狀態", "無"),
                    收款支付對象=item_data.get("收款支付對象", ""),
                    附註=""
                )

                entries.append(entry)

            assign_transaction_ids(entries, batch_id)
            if len(entries) > 1:
                total = len(entries)
                for idx, entry in enumerate(entries, start=1):
                    entry.附註 = f"多項目支出 {idx}/{total} 批次ID:{batch_id}"

            result = MultiExpenseResult(
                intent="multi_bookkeeping",
                entries=entries
            )
            return result

        elif intent == "cashflow_intents":
            cashflow_items = data.get("cashflow_items", [])
            if not cashflow_items:
                fallback_intent = detect_cashflow_intent(user_message)
                cashflow_items = (
                    fallback_cashflow_items_from_message(user_message, fallback_intent)
                    if fallback_intent
                    else []
                )
            return process_cashflow_items(cashflow_items, user_message, user_id=user_id)

        elif intent == "update_last_entry":
            # 修改上一筆記帳：提取要更新的欄位
            fields_to_update = data.get("fields_to_update", {})
            if count_update_fields(base_message) > 1:
                return MultiExpenseResult(
                    intent="error",
                    error_message="一次只允許更新一個欄位，請分開修改。"
                )

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
                "幣別": "原幣別",
                "對象": "收款支付對象",
                "狀態": "代墊狀態",
            }
            field_name = field_aliases.get(field_name, field_name)

            allowed_fields = {
                "品項",
                "分類",
                "專案",
                "原幣金額",
                "原幣別",
                "匯率",
                "付款方式",
                "明細說明",
                "必要性",
                "收款支付對象",
                "代墊狀態",
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

            if field_name == "必要性":
                from app.shared.necessity_resolver import normalize_necessity
                field_value = normalize_necessity(str(field_value), tx_type="支出")

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

            if field_name == "匯率":
                try:
                    field_value = float(field_value)
                except (TypeError, ValueError):
                    return MultiExpenseResult(
                        intent="error",
                        error_message="匯率格式錯誤，請提供正確數字。"
                    )

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
        import traceback
        logger.error(f"GPT API error in process_multi_expense: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return MultiExpenseResult(
            intent="error",
            error_message=f"系統處理訊息時發生錯誤：{str(e)}"
        )
