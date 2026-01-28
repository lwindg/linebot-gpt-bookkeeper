# -*- coding: utf-8 -*-
"""
Unit tests for foreign currency receipt conversion.
"""

from app.pipeline.image_flow import ImageItem, build_image_envelope, process_image_envelope


def test_receipt_fx_conversion(monkeypatch):
    items = [ImageItem(item="WSJ", amount=4.99, currency="USD", date="2025-11-15")]
    envelope = build_image_envelope(items, payment_method="信用卡")

    monkeypatch.setattr(
        "app.pipeline.image_flow.ExchangeRateService.get_rate",
        lambda _self, _currency: 31.5,
    )

    result = process_image_envelope(envelope, skip_gpt=True)

    assert result.intent == "multi_bookkeeping"
    assert len(result.entries) == 1
    entry = result.entries[0]
    assert entry.原幣別 == "USD"
    assert entry.匯率 == 31.5
