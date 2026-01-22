# -*- coding: utf-8 -*-
"""
Transaction Type Enum for Parser-first Architecture (T007)

定義所有交易類型，Parser 和 AI Enrichment 共用。
"""

from enum import Enum


class TransactionType(Enum):
    """交易類型 Enum"""
    
    EXPENSE = "expense"           # 一般支出
    ADVANCE_PAID = "advance_paid" # 代墊（我先付）
    ADVANCE_DUE = "advance_due"   # 需支付（他人先付）
    INCOME = "income"             # 收入
    TRANSFER = "transfer"         # 轉帳（現金流）
    CARD_PAYMENT = "card_payment" # 繳卡費（現金流）
    WITHDRAWAL = "withdrawal"     # 提款（現金流）

    @classmethod
    def is_cashflow(cls, tx_type: "TransactionType") -> bool:
        """判斷是否為現金流類型"""
        return tx_type in (cls.TRANSFER, cls.CARD_PAYMENT, cls.WITHDRAWAL, cls.INCOME)

    @classmethod
    def is_advance(cls, tx_type: "TransactionType") -> bool:
        """判斷是否為代墊相關類型"""
        return tx_type in (cls.ADVANCE_PAID, cls.ADVANCE_DUE)

    @classmethod
    def from_string(cls, value: str) -> "TransactionType":
        """從字串轉換為 TransactionType"""
        try:
            return cls(value.lower())
        except ValueError:
            raise ValueError(f"Unknown transaction type: {value}")
