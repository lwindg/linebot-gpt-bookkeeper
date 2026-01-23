# -*- coding: utf-8 -*-
"""
Integration tests for parser module.
"""

import pytest
from datetime import datetime
from zoneinfo import ZoneInfo

from app.parser import parse, ParserError, ParserErrorCode, TransactionType


class TestParserIntegration:
    """End-to-end tests for parse() function."""

    @pytest.fixture
    def taipei_now(self):
        """Fixed datetime for testing."""
        return datetime(2026, 1, 23, 12, 0, 0, tzinfo=ZoneInfo("Asia/Taipei"))

    # === Basic expense parsing ===

    def test_simple_expense(self, taipei_now):
        """午餐 80 現金"""
        envelope = parse("午餐 80 現金", context_date=taipei_now)
        assert len(envelope.transactions) == 1
        tx = envelope.transactions[0]
        assert tx.type == TransactionType.EXPENSE
        assert tx.amount == 80.0
        assert tx.payment_method == "現金"

    def test_expense_no_payment(self, taipei_now):
        """午餐 80 -> payment_method = NA"""
        envelope = parse("午餐 80", context_date=taipei_now)
        tx = envelope.transactions[0]
        assert tx.payment_method == "NA"

    # === Multi-item splitting ===

    def test_multi_item_comma(self, taipei_now):
        """午餐 80, 飲料 50"""
        envelope = parse("午餐 80, 飲料 50", context_date=taipei_now)
        assert len(envelope.transactions) == 2
        assert envelope.transactions[0].amount == 80.0
        assert envelope.transactions[1].amount == 50.0

    def test_multi_item_newline(self, taipei_now):
        """午餐 80\\n飲料 50"""
        envelope = parse("午餐 80\n飲料 50", context_date=taipei_now)
        assert len(envelope.transactions) == 2

    # === Cashflow intents ===

    def test_transfer_intent(self, taipei_now):
        """轉帳 500 給老公"""
        envelope = parse("轉帳 500 給老公", context_date=taipei_now)
        tx = envelope.transactions[0]
        assert tx.type == TransactionType.TRANSFER
        assert tx.amount == 500.0

    def test_income_intent(self, taipei_now):
        """薪水 50000"""
        envelope = parse("薪水 50000", context_date=taipei_now)
        tx = envelope.transactions[0]
        assert tx.type == TransactionType.INCOME

    def test_card_payment_intent(self, taipei_now):
        """繳卡費 12000"""
        envelope = parse("繳卡費 12000", context_date=taipei_now)
        tx = envelope.transactions[0]
        assert tx.type == TransactionType.CARD_PAYMENT

    def test_withdrawal_intent(self, taipei_now):
        """ATM 提款 3000"""
        envelope = parse("ATM 提款 3000", context_date=taipei_now)
        tx = envelope.transactions[0]
        assert tx.type == TransactionType.WITHDRAWAL

    # === Advance status ===

    def test_advance_paid(self, taipei_now):
        """幫同事墊便當 100"""
        envelope = parse("幫同事墊便當 100", context_date=taipei_now)
        tx = envelope.transactions[0]
        assert tx.type == TransactionType.ADVANCE_PAID
        assert tx.counterparty == "同事"

    def test_advance_due(self, taipei_now):
        """弟代訂披薩 500"""
        envelope = parse("弟代訂披薩 500", context_date=taipei_now)
        tx = envelope.transactions[0]
        assert tx.type == TransactionType.ADVANCE_DUE
        assert tx.counterparty == "弟"

    # === Date extraction ===

    def test_yesterday(self, taipei_now):
        """昨天早餐 50"""
        envelope = parse("昨天早餐 50", context_date=taipei_now)
        tx = envelope.transactions[0]
        assert tx.date == "01/22"

    def test_explicit_date(self, taipei_now):
        """1/20 午餐 80"""
        envelope = parse("1/20 午餐 80", context_date=taipei_now)
        tx = envelope.transactions[0]
        assert tx.date == "01/20"

    # === Payment method detection ===

    def test_payment_flygo(self, taipei_now):
        """灰狗 1200"""
        envelope = parse("灰狗 1200", context_date=taipei_now)
        tx = envelope.transactions[0]
        assert tx.payment_method == "FlyGo 信用卡"

    def test_payment_costco(self, taipei_now):
        """Costco 3000"""
        envelope = parse("Costco 3000", context_date=taipei_now)
        tx = envelope.transactions[0]
        assert tx.payment_method == "富邦 Costco"

    # === Error cases ===

    def test_empty_message_error(self, taipei_now):
        """空訊息應拋出錯誤"""
        with pytest.raises(ParserError) as exc_info:
            parse("", context_date=taipei_now)
        assert exc_info.value.code == ParserErrorCode.EMPTY_MESSAGE

    def test_missing_amount_error(self, taipei_now):
        """只有品項沒有金額"""
        with pytest.raises(ParserError) as exc_info:
            parse("午餐", context_date=taipei_now)
        assert exc_info.value.code == ParserErrorCode.MISSING_AMOUNT

    # === Envelope structure ===

    def test_envelope_structure(self, taipei_now):
        """驗證 envelope 結構"""
        envelope = parse("午餐 80 現金", context_date=taipei_now)
        assert envelope.version == "1.0"
        assert envelope.source_text == "午餐 80 現金"
        assert envelope.parse_timestamp is not None
        assert envelope.constraints["classification_must_be_in_list"] is True
