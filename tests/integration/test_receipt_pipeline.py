# -*- coding: utf-8 -*-
"""
Integration tests for image receipt pipeline.
"""

from app.services.image_handler import ReceiptItem, build_image_authoritative_envelope
from app.pipeline.image_flow import process_image_envelope


def test_image_receipt_pipeline_twd_skip_gpt():
    receipt_items = [
        ReceiptItem(品項="咖啡", 原幣金額=50, 原幣別="TWD", 付款方式="現金", 日期="2025-11-15"),
        ReceiptItem(品項="三明治", 原幣金額=80, 原幣別="TWD", 付款方式="現金", 日期="2025-11-15"),
    ]
    envelope = build_image_authoritative_envelope(receipt_items)

    result = process_image_envelope(envelope, skip_gpt=True)

    assert result.intent == "multi_bookkeeping"
    assert len(result.entries) == 2
    assert result.entries[0].付款方式 == "現金"
    assert result.entries[0].原幣別 == "TWD"
    assert result.entries[0].匯率 == 1.0


def test_image_receipt_pipeline_foreign_currency(monkeypatch):
    receipt_items = [
        ReceiptItem(品項="WSJ", 原幣金額=4.99, 原幣別="USD", 付款方式="信用卡", 日期="2025-11-15"),
    ]
    envelope = build_image_authoritative_envelope(receipt_items)

    monkeypatch.setattr(
        "app.pipeline.image_flow.ExchangeRateService.get_rate",
        lambda _self, _currency: 31.5,
    )

    result = process_image_envelope(envelope, skip_gpt=True)

    assert result.intent == "multi_bookkeeping"
    assert len(result.entries) == 1
    assert result.entries[0].原幣別 == "USD"
    assert result.entries[0].匯率 == 31.5
