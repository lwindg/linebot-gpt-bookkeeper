# -*- coding: utf-8 -*-
"""
Parser Module for Parser-first Architecture (T006)

此模組負責將使用者訊息解析為權威 JSON (Authoritative Envelope)。
AI Enrichment 不得修改 Parser 輸出的權威欄位。

主要入口：
- parse(message: str) -> AuthoritativeEnvelope

Usage:
    from app.parser import parse
    envelope = parse("午餐80現金")
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from app.parser.types import TransactionType
from app.parser.errors import ParserError, ParserErrorCode


@dataclass
class Transaction:
    """單筆交易資料（Parser 輸出）"""
    
    id: str                                # 交易 ID (e.g., 't1', 't2')
    type: TransactionType                  # 交易類型
    raw_item: str                          # 原始品項文字
    amount: float                          # 金額
    currency: str = "TWD"                  # 幣別
    payment_method: str = "N/A"             # 付款方式
    counterparty: str = ""                 # 收款/支付對象
    date: Optional[str] = None             # 日期
    time: Optional[str] = None             # 時間 (Task 5)
    accounts: dict = field(default_factory=lambda: {"from": None, "to": None})
    notes_raw: str = ""                    # 原文中的額外描述


@dataclass
class AuthoritativeEnvelope:
    """Parser 輸出的權威 JSON 格式"""
    
    version: str = "1.0"
    source_text: str = ""
    parse_timestamp: str = ""
    transactions: list[Transaction] = field(default_factory=list)
    constraints: dict = field(default_factory=lambda: {
        "classification_must_be_in_list": True,
        "do_not_modify_authoritative_fields": True,
        "unknown_payment_method_policy": "error"
    })

    def to_dict(self) -> dict:
        """轉換為字典格式"""
        return {
            "version": self.version,
            "source_text": self.source_text,
            "parse_timestamp": self.parse_timestamp,
            "transactions": [
                {
                    "id": tx.id,
                    "type": tx.type.value,
                    "raw_item": tx.raw_item,
                    "amount": tx.amount,
                    "currency": tx.currency,
                    "payment_method": tx.payment_method,
                    "counterparty": tx.counterparty,
                    "date": tx.date,
                    "accounts": tx.accounts,
                    "notes_raw": tx.notes_raw,
                }
                for tx in self.transactions
            ],
            "constraints": self.constraints,
        }


def parse(message: str, *, context_date: Optional[datetime] = None) -> AuthoritativeEnvelope:
    """
    解析使用者訊息為權威 JSON。
    
    Args:
        message: 使用者輸入的記帳訊息
        context_date: 執行日期（用於解析「今天」等語義日期）
    
    Returns:
        AuthoritativeEnvelope: 解析後的權威 JSON
    
    Raises:
        ParserError: 解析失敗
    """
    from app.parser.extract_amount import extract_amount_and_currency
    from app.parser.extract_payment import extract_payment_method, clean_item_text
    from app.parser.extract_date import extract_date
    from app.parser.extract_time import extract_time, clean_time_text
    from app.parser.extract_advance import extract_advance_status
    from app.parser.extract_cashflow import detect_cashflow_intent, extract_transfer_accounts
    from app.parser.split_items import split_items
    from app.parser.build_envelope import build_envelope
    
    if not message or not message.strip():
        raise ParserError.from_code(ParserErrorCode.EMPTY_MESSAGE)
    
    message = message.strip()
    taipei_tz = ZoneInfo("Asia/Taipei")
    now = context_date or datetime.now(taipei_tz)
    
    # 1. 偵測是否為現金流意圖
    cashflow_intent = detect_cashflow_intent(message)
    
    # 2. 切割多項目（僅一般支出支援多項目）
    if cashflow_intent:
        items = [message]  # 現金流不切割
    else:
        items = split_items(message)
    
    # 3. 解析每個項目
    transactions: list[Transaction] = []
    for idx, item_text in enumerate(items, start=1):
        tx_id = f"t{idx}"
        
        # 抽取金額與幣別
        amount, currency, remaining = extract_amount_and_currency(item_text)
        if amount <= 0:
            raise ParserError.from_code(ParserErrorCode.MISSING_AMOUNT)
        
        # 抽取付款方式
        payment_method = extract_payment_method(item_text)
        
        # 抽取日期
        date_str = extract_date(item_text, now)
        
        # 抽取時間 (Task 5)
        time_str = extract_time(item_text)
        
        # 抽取代墊狀態與對象
        advance_status, counterparty = extract_advance_status(item_text)
        
        # 判斷交易類型
        if cashflow_intent:
            tx_type = TransactionType(cashflow_intent)
        elif advance_status == "代墊":
            tx_type = TransactionType.ADVANCE_PAID
        elif advance_status == "需支付":
            tx_type = TransactionType.ADVANCE_DUE
        else:
            tx_type = TransactionType.EXPENSE
        
        # 清理品項文字（移除付款方式關鍵字與時間）
        raw_item = remaining or item_text
        cleaned_item = clean_item_text(raw_item, payment_method)
        cleaned_item = clean_time_text(cleaned_item)
        if not cleaned_item or not cleaned_item.strip():
            raise ParserError.from_code(ParserErrorCode.MISSING_ITEM)
        
        # 建立交易（現金流補上帳戶資訊）
        accounts = {"from": None, "to": None}
        if tx_type in (TransactionType.TRANSFER, TransactionType.CARD_PAYMENT):
            source_account, target_account = extract_transfer_accounts(item_text)
            accounts = {"from": source_account, "to": target_account}

        # 建立交易
        tx = Transaction(
            id=tx_id,
            type=tx_type,
            raw_item=cleaned_item,
            amount=amount,
            currency=currency,
            payment_method=payment_method,
            counterparty=counterparty,
            date=date_str,
            time=time_str,
            accounts=accounts,
        )
        transactions.append(tx)

    # 4. 多項目付款方式一致性檢查（僅一般支出）
    if not cashflow_intent and len(transactions) > 1:
        payments = {tx.payment_method for tx in transactions if tx.payment_method != "N/A"}
        if len(payments) > 1:
            raise ParserError.from_code(ParserErrorCode.MIXED_PAYMENT_METHOD)
    
    # 5. 組裝 Envelope
    envelope = build_envelope(
        source_text=message,
        transactions=transactions,
        timestamp=now,
    )
    
    return envelope


# Export
__all__ = [
    "parse",
    "Transaction",
    "AuthoritativeEnvelope",
    "TransactionType",
    "ParserError",
    "ParserErrorCode",
]
