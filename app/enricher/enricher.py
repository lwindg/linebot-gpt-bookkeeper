# -*- coding: utf-8 -*-
"""
Core Enricher Logic (T018)

對 Parser 輸出進行 AI Enrichment，補充分類、專案、必要性、明細說明。
"""

import logging
from typing import Optional

from app.parser import AuthoritativeEnvelope, Transaction, TransactionType
from app.enricher.validator import validate_category
from .types import EnrichedTransaction, EnrichedEnvelope
from .gpt_client import call_gpt_enrichment

logger = logging.getLogger(__name__)


def _transaction_to_dict(tx: Transaction) -> dict:
    """將 Transaction dataclass 轉為 dict 供 GPT client 使用"""
    return {
        "id": tx.id,
        "type": tx.type.value,
        "raw_item": tx.raw_item,
        "amount": tx.amount,
        "currency": tx.currency,
        "payment_method": tx.payment_method,
        "counterparty": tx.counterparty,
        "date": tx.date,
    }




def _cashflow_category(tx_type: TransactionType) -> str:
    """Return fixed category for cashflow types."""
    if tx_type == TransactionType.WITHDRAWAL:
        return "提款"
    if tx_type == TransactionType.TRANSFER:
        return "轉帳"
    if tx_type == TransactionType.CARD_PAYMENT:
        return "繳卡費"
    if tx_type == TransactionType.INCOME:
        return "收入"
    return "未分類"


def _merge_enrichment(
    tx: Transaction,
    enrichment: dict,
) -> EnrichedTransaction:
    """
    合併 Parser 權威欄位與 AI Enrichment 結果。
    
    Args:
        tx: Parser 輸出的 Transaction
        enrichment: AI 回傳的 enrichment dict（包含 分類, 專案, 必要性, 明細說明）
    
    Returns:
        EnrichedTransaction: 合併後的完整交易
    """
    # 現金流分類固定，不交給 GPT
    if TransactionType.is_cashflow(tx.type):
        category = _cashflow_category(tx.type)
    else:
        # 驗證分類
        category = validate_category(enrichment.get("分類", "未分類"))
    
    return EnrichedTransaction(
        # Parser 權威欄位
        id=tx.id,
        type=tx.type,
        raw_item=tx.raw_item,
        amount=tx.amount,
        currency=tx.currency,
        payment_method=tx.payment_method,
        counterparty=tx.counterparty,
        date=tx.date,
        accounts_from=tx.accounts.get("from") if tx.accounts else None,
        accounts_to=tx.accounts.get("to") if tx.accounts else None,
        fx_rate=1.0,
        # AI Enrichment 欄位
        分類=category,
        專案=enrichment.get("專案", "日常"),
        必要性=enrichment.get("必要性", "必要日常支出"),
        明細說明=enrichment.get("明細說明", ""),
    )


def enrich(
    envelope: AuthoritativeEnvelope,
    *,
    skip_gpt: bool = False,
    mock_enrichment: Optional[list[dict]] = None,
) -> EnrichedEnvelope:
    """
    對 Parser 輸出進行 AI Enrichment。
    
    Args:
        envelope: Parser 輸出的 AuthoritativeEnvelope
        skip_gpt: 若為 True，跳過 GPT 呼叫，使用預設值
        mock_enrichment: 用於測試的 mock enrichment 資料
    
    Returns:
        EnrichedEnvelope: 包含完整 enriched 交易的結果
    
    流程：
    1. 將 transactions 轉換為 GPT prompt 格式
    2. 呼叫 GPT API（或使用 mock）
    3. 合併 Parser 權威欄位 + AI Enrichment 結果
    4. 驗證分類是否在允許清單內
    5. 回傳 EnrichedEnvelope
    """
    transactions = envelope.transactions
    
    # 建立 id -> enrichment 的對照表
    enrichment_map: dict[str, dict] = {}
    
    if mock_enrichment is not None:
        # 使用 mock 資料（測試用）
        for item in mock_enrichment:
            enrichment_map[item["id"]] = item
    elif skip_gpt:
        # 跳過 GPT，使用預設值
        for tx in transactions:
            enrichment_map[tx.id] = {
                "id": tx.id,
                "分類": "未分類",
                "專案": "日常",
                "必要性": "必要日常支出",
                "明細說明": "",
            }
    else:
        # 現金流不交給 GPT 分類；只針對非現金流交易呼叫 GPT
        non_cashflow = [tx for tx in transactions if not TransactionType.is_cashflow(tx.type)]
        cashflow = [tx for tx in transactions if TransactionType.is_cashflow(tx.type)]

        if non_cashflow:
            tx_dicts = [_transaction_to_dict(tx) for tx in non_cashflow]
            gpt_result = call_gpt_enrichment(tx_dicts, envelope.source_text)
            for item in gpt_result.get("enrichment", []):
                enrichment_map[item["id"]] = item

        for tx in cashflow:
            enrichment_map[tx.id] = {
                "id": tx.id,
                "分類": _cashflow_category(tx.type),
                "專案": "日常",
                "必要性": "必要日常支出",
                "明細說明": "",
            }
    
    # 合併結果
    enriched_transactions = []
    for tx in transactions:
        enrichment = enrichment_map.get(tx.id, {
            "id": tx.id,
            "分類": "未分類",
            "專案": "日常",
            "必要性": "必要日常支出",
            "明細說明": "",
        })
        enriched_tx = _merge_enrichment(tx, enrichment)
        enriched_transactions.append(enriched_tx)
    
    return EnrichedEnvelope(
        version=envelope.version,
        source_text=envelope.source_text,
        parse_timestamp=envelope.parse_timestamp,
        transactions=enriched_transactions,
    )
