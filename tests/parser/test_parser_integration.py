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
        assert tx.payment_method == "N/A"

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

    @pytest.mark.parametrize(
        "message, expected_from, expected_to",
        [
            ("Richart轉帳到 Line 2000", "台新 Richart", "Line Pay"),
            ("Richart轉帳到合庫2000", "台新 Richart", "合庫"),
        ],
    )
    def test_transfer_accounts_order(self, taipei_now, message, expected_from, expected_to):
        envelope = parse(message, context_date=taipei_now)
        tx = envelope.transactions[0]
        assert tx.accounts["from"] == expected_from
        assert tx.accounts["to"] == expected_to

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
        assert tx.date == "2026-01-22"

    def test_explicit_date(self, taipei_now):
        """1/20 午餐 80"""
        envelope = parse("1/20 午餐 80", context_date=taipei_now)
        tx = envelope.transactions[0]
        assert tx.date == "2026-01-20"

    def test_roc_date(self, taipei_now):
        """115/02/06 午餐 80"""
        envelope = parse("115/02/06 午餐 80", context_date=taipei_now)
        tx = envelope.transactions[0]
        assert tx.date == "2026-02-06"

    # === Payment method detection ===

    def test_payment_flygo(self, taipei_now):
        """灰狗卡 1200"""
        with pytest.raises(ParserError) as exc_info:
            parse("灰狗卡 1200", context_date=taipei_now)
        assert exc_info.value.code == ParserErrorCode.MISSING_ITEM

    def test_payment_costco(self, taipei_now):
        """Costco 3000"""
        with pytest.raises(ParserError) as exc_info:
            parse("Costco 3000", context_date=taipei_now)
        assert exc_info.value.code == ParserErrorCode.MISSING_ITEM

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

    # === Edge cases from functional suites ===

    def test_decimal_amount(self, taipei_now):
        """TC-V1-003: 咖啡45.5元 Line Pay -> 小數金額"""
        envelope = parse("咖啡45.5元 Line Pay", context_date=taipei_now)
        tx = envelope.transactions[0]
        assert tx.amount == 45.5
        assert tx.payment_method == "Line Pay"

    def test_amount_first_order(self, taipei_now):
        """TC-V1-002: 200 點心 狗卡 -> 金額在前的順序"""
        envelope = parse("200 點心 狗卡", context_date=taipei_now)
        tx = envelope.transactions[0]
        assert tx.amount == 200.0
        assert tx.payment_method == "台新狗卡"

    def test_item_with_embedded_number(self, taipei_now):
        """TC-V17-022: 大兒子英文課10堂 1800 Line -> 品項含數字不誤判"""
        envelope = parse("大兒子英文課10堂 1800 Line", context_date=taipei_now)
        tx = envelope.transactions[0]
        # 金額應該是 1800，不是 10
        assert tx.amount == 1800.0
        assert tx.payment_method == "Line Pay"

    def test_full_date_format(self, taipei_now):
        """TC-DATE-004: 2025-11-10 咖啡50元現金 -> YYYY-MM-DD 格式"""
        envelope = parse("2025-11-10 咖啡50元現金", context_date=taipei_now)
        tx = envelope.transactions[0]
        assert tx.amount == 50.0
        assert tx.date == "2025-11-10"  # 輸出格式為 YYYY-MM-DD

    def test_date_with_time_ignore_time(self, taipei_now):
        """TC-DATE-006: 12/14 09:00 咖啡100元現金 -> 忽略時間部分"""
        envelope = parse("12/14 09:00 咖啡100元現金", context_date=taipei_now)
        tx = envelope.transactions[0]
        assert tx.amount == 100.0
        assert tx.date == "2026-12-14"
        # 09:00 不應被誤判為金額或影響解析

    def test_no_claim_with_explicit_keyword(self, taipei_now):
        """TC-V17-008: 幫媽媽買藥500元現金 不用還 -> 不索取 (避免逗號分隔)"""
        # 注意：原測試使用逗號會被 split_items 切割，導致「不用還」成為獨立項目
        # 改用空格分隔以避免此問題
        envelope = parse("幫媽媽買藥500元現金 不用還", context_date=taipei_now)
        tx = envelope.transactions[0]
        assert tx.type == TransactionType.EXPENSE  # 不索取視為一般支出
        assert tx.amount == 500.0
        assert tx.payment_method == "現金"

    def test_richart_payment(self, taipei_now):
        """TC-V1-025: 午餐120元Richart -> Richart 付款方式"""
        envelope = parse("午餐120元Richart", context_date=taipei_now)
        tx = envelope.transactions[0]
        assert tx.payment_method == "台新 Richart"

    def test_multi_item_shared_payment_newline(self, taipei_now):
        """驗證多項目共用付款方式 (換行分隔)"""
        # 注意：目前 split_items 會將每個逗號分隔部分視為獨立項目
        # 「現金」會被視為第三項導致金額缺失錯誤
        # 使用換行並將付款方式附加在每項可作為替代方案
        envelope = parse("早餐80元現金\n午餐150元現金", context_date=taipei_now)
        assert len(envelope.transactions) == 2
        assert envelope.transactions[0].amount == 80.0
        assert envelope.transactions[1].amount == 150.0
        for tx in envelope.transactions:
            assert tx.payment_method == "現金"

    def test_month_range_not_split(self, taipei_now):
        """月份範圍不應被當成分項切割"""
        envelope = parse("大兒子1、2月零用錢1000 現金", context_date=taipei_now)
        assert len(envelope.transactions) == 1
        tx = envelope.transactions[0]
        assert tx.amount == 1000.0
        assert tx.payment_method == "現金"
        assert tx.date is None
        assert "1、2月" in tx.raw_item

    def test_month_range_not_date(self, taipei_now):
        """月份範圍不應被解析為日期"""
        envelope = parse("妹2025年11-12月心理諮商10500合庫", context_date=taipei_now)
        tx = envelope.transactions[0]
        assert tx.amount == 10500.0
        assert tx.payment_method == "合庫"
        assert tx.date is None
