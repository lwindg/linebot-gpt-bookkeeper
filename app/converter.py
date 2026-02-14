# -*- coding: utf-8 -*-
"""
Format Converter (Phase 3)

將 Parser-first 輸出轉換為舊版 gpt_processor 格式，確保向後相容。
"""

from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

from app.parser import TransactionType
from app.enricher import EnrichedEnvelope, EnrichedTransaction
from app.gpt.types import BookkeepingEntry, MultiExpenseResult
from app.pipeline.normalize import build_batch_id, assign_transaction_ids
from app.services.lock_service import LockService
from app.services.exchange_rate import ExchangeRateService
from app.services.kv_store import KVStore


def _type_to_advance_status(tx_type: TransactionType, counterparty: str) -> str:
    """將 TransactionType 轉換為代墊狀態"""
    if tx_type == TransactionType.ADVANCE_PAID:
        return "代墊"
    elif tx_type == TransactionType.ADVANCE_DUE:
        return "需支付"
    elif counterparty:
        # 有對象但不是代墊類型 -> 可能是不索取
        return "不索取"
    return "無"


def _enriched_tx_to_entry(
    tx: EnrichedTransaction,
    shared_date: Optional[str] = None,
    shared_payment: Optional[str] = None,
    batch_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> BookkeepingEntry:
    """將 EnrichedTransaction 轉換為 BookkeepingEntry"""
    
    # 決定日期
    has_explicit_date = bool(tx.date or shared_date)
    date_str = tx.date or shared_date
    if not date_str:
        taipei_tz = ZoneInfo("Asia/Taipei")
        date_str = datetime.now(taipei_tz).strftime("%Y-%m-%d")

    # 生成交易 ID（若已提供批次ID，優先使用）
    transaction_id = batch_id or build_batch_id(
        date_str,
        tx.time,
        item=tx.raw_item,
        use_current_time=not has_explicit_date,
    )

    # 判斷代墊狀態
    advance_status = _type_to_advance_status(tx.type, tx.counterparty)

    # 判斷交易類型 (支出/收入/轉帳/提款)
    if tx.type == TransactionType.INCOME:
        tx_type = "收入"
    elif tx.type == TransactionType.WITHDRAWAL:
        tx_type = "提款"
    elif tx.type == TransactionType.TRANSFER:
        tx_type = "支出" # 轉帳的第一筆(來源)視為支出 (由來源帳戶支出)
    elif tx.type == TransactionType.CARD_PAYMENT:
        tx_type = "支出"
    else:
        tx_type = "支出"

    # 決定付款方式 (來自 Parser 或共用)
    final_payment = tx.payment_method if tx.payment_method != "NA" else shared_payment or "NA"

    # 特殊處理：轉帳 (TRANSFER) 產生雙分錄
    # 邏輯：Entry 1 (轉出/來源帳戶) + Entry 2 (轉入/收入)
    if tx.type == TransactionType.TRANSFER:
        outgoing_account = getattr(tx, "accounts_from", None)
        if outgoing_account:
            final_payment = outgoing_account

    # 特殊處理：繳卡費 (CARD_PAYMENT) 產生雙分錄
    if tx.type == TransactionType.CARD_PAYMENT:
        outgoing_account = getattr(tx, "accounts_from", None)
        if outgoing_account:
            final_payment = outgoing_account

    # --- Session Lock logic (v2.2.0) ---
    final_project = tx.專案
    # final_payment 已在上方決定
    final_currency = tx.currency
    final_fx_rate = tx.fx_rate

    if user_id:
        lock_service = LockService(user_id)
        
        # 1. Project Lock
        # Only apply if current project is "日常" or empty (indicating no explicit mention)
        if final_project in ("日常", ""):
            project_lock = lock_service.get_project_lock()
            if project_lock:
                final_project = project_lock
        
        # 2. Payment Method Lock & 3. Currency Lock
        # Only apply to non-cashflow transactions (EXPENSE, ADVANCE)
        if not TransactionType.is_cashflow(tx.type):
            # 2. Payment Method Lock
            # Only apply if current payment is "NA" or empty
            if final_payment in ("NA", ""):
                payment_lock = lock_service.get_payment_lock()
                if payment_lock:
                    final_payment = payment_lock

            # 3. Currency Lock (v2.4.0)
            # Only apply if current currency is "TWD" (default) or empty
            if final_currency in ("TWD", ""):
                currency_lock = lock_service.get_currency_lock()
                if currency_lock and currency_lock != "TWD":
                    final_currency = currency_lock
                    # Update exchange rate for the locked currency
                    kv = KVStore()
                    ex_service = ExchangeRateService(kv)
                    rate = ex_service.get_rate(final_currency)
                    if rate:
                        final_fx_rate = rate

    return BookkeepingEntry(
        intent="bookkeeping",
        日期=date_str,
        時間=tx.time,
        品項=tx.raw_item,
        原幣別=final_currency,
        原幣金額=tx.amount,
        匯率=final_fx_rate,
        明細說明=tx.明細說明,
        付款方式=final_payment,
        分類=tx.分類,
        專案=final_project,
        必要性=tx.必要性,
        代墊狀態=advance_status,
        收款支付對象=tx.counterparty,
        附註="",
        交易ID=transaction_id,
        交易類型=tx_type,
        response_text=None,
    )


def enriched_to_multi_result(
    envelope: EnrichedEnvelope,
    shared_payment: Optional[str] = None,
    user_id: Optional[str] = None,
) -> MultiExpenseResult:
    """
    將 EnrichedEnvelope 轉換為 MultiExpenseResult。

    Args:
        envelope: Enricher 輸出的 EnrichedEnvelope
        shared_payment: 共用付款方式（若有）
        user_id: 使用者 ID (用於讀取鎖定設定)

    Returns:
        MultiExpenseResult: 與舊版 gpt_processor 相容的格式
    """
    entries = []

    # 取得第一筆的日期作為共用日期（如有）
    shared_date = None
    shared_time = None
    if envelope.transactions:
        shared_date = envelope.transactions[0].date
        shared_time = envelope.transactions[0].time
    first_item = envelope.transactions[0].raw_item if envelope.transactions else None
    use_current_time = not bool(shared_date)
    batch_id = build_batch_id(
        shared_date or datetime.now(ZoneInfo("Asia/Taipei")).strftime("%Y-%m-%d"),
        shared_time,
        item=first_item,
        use_current_time=use_current_time,
    )

    for tx in envelope.transactions:
        entry = _enriched_tx_to_entry(tx, shared_date, shared_payment, batch_id, user_id=user_id)
        entries.append(entry)
        
        # 特殊處理：提款 (WITHDRAWAL) 產生雙分錄
        # 邏輯：Entry 1 (提款/來源帳戶) + Entry 2 (收入/現金)
        if tx.type == TransactionType.WITHDRAWAL:
            # 判斷提款目標：若來源是日圓帳戶，則提到「日圓現金」；否則提到「現金」
            target_cash = "現金"
            if "日圓" in entry.付款方式 or "日幣" in entry.付款方式:
                target_cash = "日圓現金"
            
            # 複製第一筆，修改為現金收入
            cash_entry = BookkeepingEntry(
                intent="bookkeeping",
                日期=entry.日期,
                時間=entry.時間,
                品項=entry.品項,
                原幣別=entry.原幣別,
                原幣金額=entry.原幣金額,
                匯率=entry.匯率,
                明細說明=entry.明細說明,
                付款方式=target_cash,
                分類=entry.分類,
                專案=entry.專案,
                必要性=entry.必要性,
                代墊狀態=entry.代墊狀態,
                收款支付對象=entry.收款支付對象,
                附註=entry.附註,
                交易ID=batch_id, # 先使用批次ID，稍後統一加序號
                交易類型="收入",
                response_text=None,
            )
            entries.append(cash_entry)
        # 特殊處理：轉帳 (TRANSFER) 產生雙分錄
        # 邏輯：Entry 1 (轉出/來源帳戶) + Entry 2 (轉入/收入)
        if tx.type == TransactionType.TRANSFER:
            incoming_account = getattr(tx, "accounts_to", None)
            if incoming_account:
                incoming_entry = BookkeepingEntry(
                    intent="bookkeeping",
                    日期=entry.日期,
                    時間=entry.時間,
                    品項=entry.品項,
                    原幣別=entry.原幣別,
                    原幣金額=entry.原幣金額,
                    匯率=entry.匯率,
                    明細說明=entry.明細說明,
                    付款方式=incoming_account,
                    分類=entry.分類,
                    專案=entry.專案,
                    必要性=entry.必要性,
                    代墊狀態=entry.代墊狀態,
                    收款支付對象=entry.收款支付對象,
                    附註=entry.附註,
                    交易ID=batch_id,
                    交易類型="收入",
                    response_text=None,
                )
                entries.append(incoming_entry)
        # 特殊處理：繳卡費 (CARD_PAYMENT) 產生雙分錄
        # 邏輯：Entry 1 (轉出/付款帳戶) + Entry 2 (轉入/卡片入帳)
        if tx.type == TransactionType.CARD_PAYMENT:
            incoming_account = getattr(tx, "accounts_to", None)
            incoming_payment = incoming_account or "NA"
            incoming_entry = BookkeepingEntry(
                intent="bookkeeping",
                日期=entry.日期,
                時間=entry.時間,
                品項=entry.品項,
                原幣別=entry.原幣別,
                原幣金額=entry.原幣金額,
                匯率=entry.匯率,
                明細說明=entry.明細說明,
                付款方式=incoming_payment,
                分類=entry.分類,
                專案=entry.專案,
                必要性=entry.必要性,
                代墊狀態=entry.代墊狀態,
                收款支付對象=entry.收款支付對象,
                附註=entry.附註,
                交易ID=batch_id,
                交易類型="收入",
                response_text=None,
            )
            entries.append(incoming_entry)

    # 統一設定交易ID（多筆加序號）
    assign_transaction_ids(entries, batch_id)

    # Determine result intent based on transactions
    # Legacy compatibility: specific intent for cashflow items
    is_cashflow = any(TransactionType.is_cashflow(tx.type) for tx in envelope.transactions)
    result_intent = "cashflow_intents" if is_cashflow else "multi_bookkeeping"

    return MultiExpenseResult(
        intent=result_intent,
        entries=entries,
        fields_to_update=None,
        error_message=None,
        error_reason=None,
        response_text=None,
    )
