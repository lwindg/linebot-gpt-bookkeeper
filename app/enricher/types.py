# -*- coding: utf-8 -*-
"""
Enrichment Types (Phase 2)

定義 Enricher 模組使用的資料型別。
"""

from dataclasses import dataclass, field
from typing import Optional

from app.parser.types import TransactionType


@dataclass
class EnrichedTransaction:
    """
    合併 Parser 權威欄位 + AI Enrichment 的完整交易記錄。
    
    Parser 權威欄位（不可被 AI 修改）：
    - id, type, raw_item, amount, currency, payment_method, counterparty, date
    
    AI Enrichment 欄位：
    - 分類, 專案, 必要性, 明細說明
    """
    # === Parser 權威欄位 ===
    id: str
    type: TransactionType
    raw_item: str
    amount: float
    currency: str
    payment_method: str
    counterparty: str = ""
    date: Optional[str] = None
    
    # === AI Enrichment 欄位 ===
    分類: str = ""
    專案: str = "日常"
    必要性: str = "必要日常支出"
    明細說明: str = ""

    # === FX ===
    fx_rate: float = 1.0
    
    # === 帳戶資訊（現金流用）===
    accounts_from: Optional[str] = None
    accounts_to: Optional[str] = None


@dataclass
class EnrichedEnvelope:
    """
    完整的 Enriched 結果。
    
    包含原始訊息、解析時間戳記，以及所有 Enriched 交易。
    """
    version: str
    source_text: str
    parse_timestamp: str
    transactions: list[EnrichedTransaction] = field(default_factory=list)
