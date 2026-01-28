# -*- coding: utf-8 -*-
"""
Unit tests for image pipeline flow.
"""

from app.pipeline.image_flow import (
    ImageItem,
    build_image_envelope,
    process_image_envelope,
)


def test_process_image_envelope_twd_skip_gpt():
    items = [
        ImageItem(item="咖啡", amount=50, currency="TWD", date="2025-11-15"),
        ImageItem(item="三明治", amount=80, currency="TWD", date="2025-11-15"),
    ]
    envelope = build_image_envelope(items, receipt_date="2025-11-15", payment_method="現金")

    result = process_image_envelope(envelope, skip_gpt=True)

    assert result.intent == "multi_bookkeeping"
    assert len(result.entries) == 2
    assert result.entries[0].付款方式 == "現金"
    assert result.entries[0].原幣別 == "TWD"
    assert result.entries[0].匯率 == 1.0


def test_process_image_envelope_foreign_currency(monkeypatch):
    items = [ImageItem(item="拉麵", amount=900, currency="JPY", date="2025-11-15")]
    envelope = build_image_envelope(items, payment_method="現金")

    monkeypatch.setattr(
        "app.pipeline.image_flow.ExchangeRateService.get_rate",
        lambda _self, _currency: 0.21,
    )

    result = process_image_envelope(envelope, skip_gpt=True)

    assert result.intent == "multi_bookkeeping"
    assert len(result.entries) == 1
    assert result.entries[0].原幣別 == "JPY"
    assert result.entries[0].匯率 == 0.21
