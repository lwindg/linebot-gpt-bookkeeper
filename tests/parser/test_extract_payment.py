# -*- coding: utf-8 -*-
"""
Unit tests for extract_payment cleanup.
"""

from app.parser.extract_payment import clean_item_text


def test_clean_item_text_does_not_remove_unrelated_keywords():
    cleaned = clean_item_text("買狗糧 現金", "現金")
    assert cleaned == "買狗糧"


def test_clean_item_text_keeps_card_brand_in_item_when_unrelated():
    cleaned = clean_item_text("星展咖啡 現金", "現金")
    assert cleaned == "星展咖啡"


def test_clean_item_text_removes_detected_payment_method():
    cleaned = clean_item_text("咖啡 Line Pay", "Line Pay")
    assert cleaned == "咖啡"
