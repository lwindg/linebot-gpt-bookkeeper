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
from app.gpt_processor import BookkeepingEntry, MultiExpenseResult


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


def _generate_transaction_id(date_str: Optional[str]) -> str:
    """
    生成交易 ID：YYYYMMDD-HHMMSS
    
    如果有日期則使用該日期，否則使用當前時間。
    支援格式：MM/DD, YYYY/MM/DD, YYYY-MM-DD
    """
    taipei_tz = ZoneInfo("Asia/Taipei")
    now = datetime.now(taipei_tz)
    
    if date_str:
        try:
            # 嘗試解析不同格式
            date_str = date_str.strip()
            
            # YYYY-MM-DD 或 YYYY/MM/DD 格式
            if len(date_str) >= 8 and (
                "-" in date_str[:5] or "/" in date_str[:5]
            ):
                # 統一分隔符
                normalized = date_str.replace("-", "/")
                parts = normalized.split("/")
                if len(parts) == 3:
                    year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
                    date_obj = datetime(year, month, day, tzinfo=taipei_tz)
                else:
                    date_obj = now
            # MM/DD 格式
            elif "/" in date_str:
                parts = date_str.split("/")
                if len(parts) == 2:
                    month, day = int(parts[0]), int(parts[1])
                    date_obj = datetime(now.year, month, day, tzinfo=taipei_tz)
                else:
                    date_obj = now
            else:
                date_obj = now
        except (ValueError, IndexError):
            date_obj = now
    else:
        date_obj = now
    
    return date_obj.strftime("%Y%m%d") + "-" + now.strftime("%H%M%S")


def _enriched_tx_to_entry(
    tx: EnrichedTransaction,
    shared_date: Optional[str] = None,
    shared_payment: Optional[str] = None,
) -> BookkeepingEntry:
    """將 EnrichedTransaction 轉換為 BookkeepingEntry"""
    
    # 決定日期
    date_str = tx.date or shared_date
    
    # 生成交易 ID
    transaction_id = _generate_transaction_id(date_str)
    
    # 判斷代墊狀態
    advance_status = _type_to_advance_status(tx.type, tx.counterparty)
    
    # 判斷交易類型 (支出/收入/轉帳/提款)
    if tx.type == TransactionType.INCOME:
        tx_type = "收入"
    elif tx.type == TransactionType.WITHDRAWAL:
        tx_type = "提款"
    elif tx.type in (TransactionType.TRANSFER, TransactionType.CARD_PAYMENT):
        tx_type = "轉帳"
    else:
        tx_type = "支出"
    
    return BookkeepingEntry(
        intent="bookkeeping",
        日期=date_str,
        時間=None,
        品項=tx.raw_item,
        原幣別=tx.currency,
        原幣金額=tx.amount,
        明細說明=tx.明細說明,
        付款方式=tx.payment_method if tx.payment_method != "NA" else shared_payment or "NA",
        分類=tx.分類,
        專案=tx.專案,
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
) -> MultiExpenseResult:
    """
    將 EnrichedEnvelope 轉換為 MultiExpenseResult。
    
    Args:
        envelope: Enricher 輸出的 EnrichedEnvelope
        shared_payment: 共用付款方式（若有）
    
    Returns:
        MultiExpenseResult: 與舊版 gpt_processor 相容的格式
    """
    entries = []
    
    # 取得第一筆的日期作為共用日期（如有）
    shared_date = None
    if envelope.transactions:
        shared_date = envelope.transactions[0].date
    
    for tx in envelope.transactions:
        entry = _enriched_tx_to_entry(tx, shared_date, shared_payment)
        entries.append(entry)
    
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
