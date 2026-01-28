# -*- coding: utf-8 -*-
"""
Tests for image authoritative envelope builder.
"""

from app.services.image_handler import ReceiptItem, build_image_authoritative_envelope


def test_build_image_envelope_shared_date_and_payment():
    items = [
        ReceiptItem(品項="咖啡", 原幣金額=50, 原幣別="TWD", 付款方式="現金", 日期="2025-11-15"),
        ReceiptItem(品項="三明治", 原幣金額=80, 原幣別="TWD", 付款方式="現金", 日期="2025-11-15"),
    ]

    envelope = build_image_authoritative_envelope(items)

    assert envelope.receipt_date == "2025-11-15"
    assert envelope.payment_method == "現金"
    assert len(envelope.items) == 2
    assert envelope.items[0].item == "咖啡"
    assert envelope.items[1].item == "三明治"


def test_build_image_envelope_multiple_dates():
    items = [
        ReceiptItem(品項="水費", 原幣金額=300, 原幣別="TWD", 付款方式="信用卡", 日期="2025-10-01"),
        ReceiptItem(品項="電費", 原幣金額=500, 原幣別="TWD", 付款方式="信用卡", 日期="2025-11-01"),
    ]

    envelope = build_image_authoritative_envelope(items)

    assert envelope.receipt_date is None
    assert envelope.payment_method == "信用卡"
    assert [item.date for item in envelope.items] == ["2025-10-01", "2025-11-01"]


def test_build_image_envelope_missing_payment():
    items = [
        ReceiptItem(品項="咖啡", 原幣金額=50, 原幣別="TWD", 日期="2025-11-15"),
        ReceiptItem(品項="三明治", 原幣金額=80, 原幣別="TWD", 日期="2025-11-15"),
    ]

    envelope = build_image_authoritative_envelope(items)

    assert envelope.payment_method is None
    assert envelope.receipt_date == "2025-11-15"
