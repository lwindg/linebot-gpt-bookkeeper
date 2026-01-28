# -*- coding: utf-8 -*-
"""
Image pipeline data structures and helpers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from app.enricher.receipt_batch import enrich_receipt_items
from app.enricher.types import EnrichedEnvelope, EnrichedTransaction
from app.gpt.types import MultiExpenseResult
from app.parser.types import TransactionType
from app.services.exchange_rate import ExchangeRateService
from app.converter import enriched_to_multi_result

@dataclass
class ImageItem:
    """Authoritative item extracted from receipt image."""
    item: str
    amount: float
    currency: str = "TWD"
    date: Optional[str] = None


@dataclass
class ImageAuthoritativeEnvelope:
    """Authoritative envelope for image receipts."""
    version: str = "1.0"
    parse_timestamp: str = ""
    receipt_date: Optional[str] = None
    payment_method: Optional[str] = None
    items: list[ImageItem] = field(default_factory=list)
    constraints: dict = field(default_factory=lambda: {
        "classification_must_be_in_list": True,
        "do_not_modify_authoritative_fields": True,
    })


def _now_iso() -> str:
    taipei_tz = ZoneInfo("Asia/Taipei")
    return datetime.now(taipei_tz).isoformat()


def build_image_envelope(
    items: list[ImageItem],
    *,
    receipt_date: Optional[str] = None,
    payment_method: Optional[str] = None,
    parse_timestamp: Optional[str] = None,
) -> ImageAuthoritativeEnvelope:
    """Build ImageAuthoritativeEnvelope with optional shared fields."""
    return ImageAuthoritativeEnvelope(
        parse_timestamp=parse_timestamp or _now_iso(),
        receipt_date=receipt_date,
        payment_method=payment_method,
        items=items,
    )


def process_image_envelope(
    envelope: ImageAuthoritativeEnvelope,
    *,
    skip_gpt: bool = False,
) -> MultiExpenseResult:
    if not envelope.items:
        return MultiExpenseResult(
            intent="error",
            entries=[],
            error_message="未識別到任何收據項目",
            error_reason="no_items",
        )

    enrichment_list = enrich_receipt_items(
        envelope.items,
        source_text="收據圖片",
        skip_gpt=skip_gpt,
    )
    enrichment_map = {item.get("id"): item for item in enrichment_list}

    exchange_rate_service = ExchangeRateService()
    enriched_transactions: list[EnrichedTransaction] = []

    for idx, item in enumerate(envelope.items, start=1):
        item_id = f"t{idx}"
        enrichment = enrichment_map.get(item_id, {})

        currency = (item.currency or "TWD").upper()
        if currency not in ExchangeRateService.SUPPORTED_CURRENCIES:
            return MultiExpenseResult(
                intent="error",
                entries=[],
                error_message=f"不支援的幣別：{currency}",
                error_reason="unsupported_currency",
            )

        fx_rate = 1.0
        if currency != "TWD":
            rate = exchange_rate_service.get_rate(currency)
            if rate is None:
                return MultiExpenseResult(
                    intent="error",
                    entries=[],
                    error_message=f"無法取得 {currency} 匯率，請稍後再試或改用新台幣記帳",
                    error_reason="rate_unavailable",
                )
            fx_rate = rate

        payment_method = envelope.payment_method or "NA"
        item_date = item.date or envelope.receipt_date

        enriched_transactions.append(EnrichedTransaction(
            id=item_id,
            type=TransactionType.EXPENSE,
            raw_item=item.item,
            amount=item.amount,
            currency=currency,
            payment_method=payment_method,
            counterparty="",
            date=item_date,
            分類=enrichment.get("分類", "未分類"),
            專案=enrichment.get("專案", "日常"),
            必要性=enrichment.get("必要性", "必要日常支出"),
            明細說明=enrichment.get("明細說明", ""),
            fx_rate=fx_rate,
        ))

    enriched_envelope = EnrichedEnvelope(
        version=envelope.version,
        source_text="image",
        parse_timestamp=envelope.parse_timestamp,
        transactions=enriched_transactions,
    )

    return enriched_to_multi_result(enriched_envelope, shared_payment=envelope.payment_method)
