import logging
import re
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from app.cashflow_rules import (
    infer_transfer_accounts,
    infer_transfer_mode,
    normalize_cashflow_payment_method,
)
from app.gpt.types import BookkeepingEntry, MultiExpenseResult
from app.pipeline.normalize import build_batch_id, assign_transaction_ids
from app.shared.project_resolver import infer_project
from app.services.lock_service import LockService

logger = logging.getLogger(__name__)

_CASHFLOW_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("card_payment", ("繳卡費", "信用卡費", "繳信用卡", "刷卡費")),
    ("transfer", ("轉帳", "匯款", "轉入", "轉出")),
    ("withdrawal", ("提款", "領現", "領錢", "ATM")),
    ("income", ("收入", "入帳", "薪水", "退款", "退費", "收款")),
)

_CASHFLOW_CATEGORIES = {
    # Keep cashflow categories as valid classification paths.
    "withdrawal": "系統/提款",
    "transfer": "系統/轉帳",
    "income": "收入/其他",
    "card_payment": "系統/繳卡費",
}

_CASHFLOW_AMOUNT_PATTERN = re.compile(r"-?\d+(?:\.\d+)?")
_SEMANTIC_DATE_TOKENS = ("今天", "昨日", "昨天", "前天", "大前天", "明天", "後天", "大後天")
_EXPLICIT_DATE_PATTERN = re.compile(r"(20\d{2})[/-](\d{1,2})[/-](\d{1,2})")


def parse_semantic_date(date_str: str, taipei_tz: ZoneInfo) -> str:
    """
    將語意日期或格式化日期轉成 YYYY-MM-DD
    """
    now = datetime.now(taipei_tz)

    semantic_dates = {
        "今天": 0,
        "昨日": -1,
        "昨天": -1,
        "前天": -2,
        "大前天": -3,
        "明天": 1,
        "後天": 2,
        "大後天": 3,
    }

    if date_str in semantic_dates:
        target_date = now + timedelta(days=semantic_dates[date_str])
        return target_date.strftime("%Y-%m-%d")

    # 處理 MM-DD 格式（補上當前年份）
    if re.match(r"^\d{1,2}-\d{1,2}$", date_str):
        parts = date_str.split("-")
        month, day = int(parts[0]), int(parts[1])
        return f"{now.year:04d}-{month:02d}-{day:02d}"

    # 處理 YYYY/M/D 或 YYYY/MM/DD 格式
    if re.match(r"^\d{4}/\d{1,2}/\d{1,2}$", date_str):
        parts = date_str.split("/")
        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
        return f"{year:04d}-{month:02d}-{day:02d}"

    # 處理 M/D 或 MM/DD 格式
    if re.match(r"^\d{1,2}/\d{1,2}$", date_str):
        parts = date_str.split("/")
        month, day = int(parts[0]), int(parts[1])
        return f"{now.year:04d}-{month:02d}-{day:02d}"

    # 其他情況，返回今天
    logger.warning(f"Unknown date format: {date_str}, using today")
    return now.strftime("%Y-%m-%d")


def detect_cashflow_intent(message: str) -> str | None:
    text = message or ""
    for intent_type, keywords in _CASHFLOW_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return intent_type
    return None


def extract_semantic_date_token(message: str) -> Optional[str]:
    text = message or ""
    for token in _SEMANTIC_DATE_TOKENS:
        if token in text:
            return token
    return None


def extract_explicit_date(message: str) -> Optional[str]:
    match = _EXPLICIT_DATE_PATTERN.search(message or "")
    if not match:
        return None
    year, month, day = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    return f"{year:04d}-{month:02d}-{day:02d}"


def normalize_cashflow_category(intent_type: str, raw_category: str) -> str:
    category = (raw_category or "").strip()
    allowed = set(_CASHFLOW_CATEGORIES.values())
    if category in allowed:
        return category
    return _CASHFLOW_CATEGORIES.get(intent_type, category or "收入/其他")


def fallback_cashflow_items_from_message(message: str, intent_type: str) -> list[dict]:
    text = message or ""
    amount_match = _CASHFLOW_AMOUNT_PATTERN.search(text)
    amount = float(amount_match.group(0)) if amount_match else None
    if not amount or amount <= 0:
        return []

    item_text = text
    if amount_match:
        item_text = item_text.replace(amount_match.group(0), "")
    item_text = re.sub(r"(元|twd|ntd|nt\$|USD|JPY|EUR|CNY|¥|円|日幣|日圓|日元|美元|美金|歐元|人民幣|台幣)", "", item_text, flags=re.IGNORECASE).strip()
    item_text = item_text or text.strip()

    payment = normalize_cashflow_payment_method(infer_transfer_accounts(text)[0] or "")
    if intent_type == "withdrawal" and payment == "N/A":
        payment = "N/A"

    return [
        {
            "現金流意圖": intent_type,
            "品項": item_text,
            "原幣金額": amount,
            "付款方式": payment,
            "分類": _CASHFLOW_CATEGORIES.get(intent_type, "收入/其他"),
        }
    ]


def process_cashflow_items(cashflow_items: list[dict], user_message: str, user_id: Optional[str] = None) -> MultiExpenseResult:
    if not cashflow_items:
        return MultiExpenseResult(
            intent="error",
            error_message="未識別到任何現金流項目"
        )

    taipei_tz = ZoneInfo("Asia/Taipei")
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
        category = normalize_cashflow_category(intent_type, category_raw)
        project = infer_project(category)

        # --- Session Lock logic (v2.2.0) ---
        if user_id:
            lock_service = LockService(user_id)
            
            # 1. Project Lock
            # Only apply if current project is "日常" or empty
            if project in ("日常", ""):
                p_lock = lock_service.get_project_lock()
                if p_lock:
                    project = p_lock
            
            # NOTE: Payment Method Lock and Currency Lock are NOT applied to cashflow transactions
            # to preserve the parsed accounts/currencies.

        date_str = item_data.get("日期")
        if isinstance(date_str, str) and date_str.strip().upper() == "N/A":
            date_str = None
        explicit_date = extract_explicit_date(user_message)
        semantic_token = extract_semantic_date_token(user_message)
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

        batch_id = build_batch_id(shared_date, item=item_name, use_current_time=not date_str)

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
            # 判斷提款目標：若來源是日圓帳戶，則提到「日圓現金」；否則提到「現金」
            target_cash = "現金"
            if "日圓" in payment_method or "日幣" in payment_method:
                target_cash = "日圓現金"
            entry_specs = [("提款", payment_method), ("收入", target_cash)]
        elif intent_type == "transfer":
            if transfer_mode == "account":
                source = transfer_source or payment_method
                target = transfer_target or "N/A"
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

        item_entries: list[BookkeepingEntry] = []
        for _idx, (tx_type, payment_method_value) in enumerate(entry_specs, start=1):
            transaction_id = batch_id
            item_entries.append(build_entry(tx_type, payment_method_value, transaction_id))
        assign_transaction_ids(item_entries, batch_id)
        entries.extend(item_entries)

    return MultiExpenseResult(
        intent="cashflow_intents",
        entries=entries
    )
