# -*- coding: utf-8 -*-
"""
Unit tests for enricher module.
"""

import pytest
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch, MagicMock

from app.parser import parse, AuthoritativeEnvelope, Transaction, TransactionType
from app.enricher import enrich, EnrichedTransaction, EnrichedEnvelope


class TestEnrichWithMock:
    """Tests for enrich() function using mock data."""

    @pytest.fixture
    def taipei_now(self):
        """Fixed datetime for testing."""
        return datetime(2026, 1, 23, 12, 0, 0, tzinfo=ZoneInfo("Asia/Taipei"))

    @pytest.fixture
    def simple_envelope(self, taipei_now):
        """Simple expense envelope for testing."""
        return parse("午餐 80 現金", context_date=taipei_now)

    def test_enrich_with_mock_data(self, simple_envelope):
        """測試使用 mock enrichment 資料"""
        mock_enrichment = [
            {
                "id": "t1",
                "分類": "家庭/餐飲/午餐",
                "專案": "日常",
                "必要性": "必要日常支出",
                "明細說明": "",
            }
        ]
        
        result = enrich(simple_envelope, mock_enrichment=mock_enrichment)
        
        assert isinstance(result, EnrichedEnvelope)
        assert len(result.transactions) == 1
        
        tx = result.transactions[0]
        assert isinstance(tx, EnrichedTransaction)
        
        # Parser 權威欄位保留
        assert tx.amount == 80.0
        assert tx.payment_method == "現金"
        assert tx.type == TransactionType.EXPENSE
        
        # AI Enrichment 欄位
        assert tx.分類 == "家庭/餐飲/午餐"
        assert tx.專案 == "日常"
        assert tx.必要性 == "必要日常支出"

    def test_enrich_skip_gpt_uses_defaults(self, simple_envelope):
        """測試 skip_gpt=True 使用預設值"""
        result = enrich(simple_envelope, skip_gpt=True)
        
        tx = result.transactions[0]
        
        # Parser 權威欄位保留
        assert tx.amount == 80.0
        assert tx.payment_method == "現金"
        
        # 預設 Enrichment 值
        assert tx.分類 == "未分類"
        assert tx.專案 == "日常"
        assert tx.必要性 == "必要日常支出"

    def test_enrich_preserves_authoritative_fields(self, taipei_now):
        """驗證權威欄位不被 Enrichment 修改"""
        envelope = parse("幫同事墊便當 100 狗卡", context_date=taipei_now)
        
        mock_enrichment = [
            {
                "id": "t1",
                "分類": "個人/餐飲",
                "專案": "日常",
                "必要性": "必要日常支出",
                "明細說明": "同事午餐",
            }
        ]
        
        result = enrich(envelope, mock_enrichment=mock_enrichment)
        tx = result.transactions[0]
        
        # 權威欄位保持不變
        assert tx.amount == 100.0
        assert tx.payment_method == "台新狗卡"
        assert tx.type == TransactionType.ADVANCE_PAID
        assert tx.counterparty == "同事"
        
        # Enrichment 欄位正確合併
        assert tx.分類 == "個人/餐飲"
        assert tx.明細說明 == "同事午餐"

    def test_enrich_cashflow_transaction(self, taipei_now):
        """現金流交易應產生有效的 EnrichedTransaction"""
        envelope = parse("合庫提款5000", context_date=taipei_now)

        result = enrich(envelope, skip_gpt=True)

        assert isinstance(result, EnrichedEnvelope)
        assert len(result.transactions) == 1
        tx = result.transactions[0]
        assert isinstance(tx, EnrichedTransaction)
        assert tx.type == TransactionType.WITHDRAWAL
        assert tx.分類 == "系統/提款"


class TestCategoryValidation:
    """Tests for category validation in enricher."""

    @pytest.fixture
    def taipei_now(self):
        return datetime(2026, 1, 23, 12, 0, 0, tzinfo=ZoneInfo("Asia/Taipei"))

    def test_valid_category_accepted(self, taipei_now):
        """有效分類應被接受"""
        envelope = parse("午餐 80 現金", context_date=taipei_now)
        
        mock_enrichment = [
            {
                "id": "t1",
                "分類": "家庭/餐飲/午餐",
                "專案": "日常",
                "必要性": "必要日常支出",
                "明細說明": "",
            }
        ]
        
        result = enrich(envelope, mock_enrichment=mock_enrichment)
        assert result.transactions[0].分類 == "家庭/餐飲/午餐"

    def test_invalid_category_normalized(self, taipei_now):
        """無效分類應被正規化或標記為未分類"""
        envelope = parse("午餐 80 現金", context_date=taipei_now)
        
        mock_enrichment = [
            {
                "id": "t1",
                "分類": "完全不存在的分類",
                "專案": "日常",
                "必要性": "必要日常支出",
                "明細說明": "",
            }
        ]
        
        result = enrich(envelope, mock_enrichment=mock_enrichment)
        # 無效分類應變為 "未分類"
        assert result.transactions[0].分類 == "未分類"

    def test_empty_category_uses_default(self, taipei_now):
        """空白分類應回傳 '未分類'，避免隨機匹配"""
        envelope = parse("午餐 80 現金", context_date=taipei_now)
        
        mock_enrichment = [
            {
                "id": "t1",
                "分類": "",  # 空白分類
                "專案": "日常",
                "必要性": "必要日常支出",
                "明細說明": "",
            }
        ]
        
        result = enrich(envelope, mock_enrichment=mock_enrichment)
        # 空白分類應直接變為 "未分類"，不應隨機匹配
        assert result.transactions[0].分類 == "未分類"

    def test_whitespace_only_category_uses_default(self, taipei_now):
        """只含空白的分類應回傳 '未分類'"""
        envelope = parse("午餐 80 現金", context_date=taipei_now)
        
        mock_enrichment = [
            {
                "id": "t1",
                "分類": "   ",  # 只有空白
                "專案": "日常",
                "必要性": "必要日常支出",
                "明細說明": "",
            }
        ]
        
        result = enrich(envelope, mock_enrichment=mock_enrichment)
        assert result.transactions[0].分類 == "未分類"


class TestMultipleTransactions:
    """Tests for enriching multiple transactions."""

    @pytest.fixture
    def taipei_now(self):
        return datetime(2026, 1, 23, 12, 0, 0, tzinfo=ZoneInfo("Asia/Taipei"))

    def test_enrich_multiple_transactions(self, taipei_now):
        """測試多筆交易 enrichment"""
        envelope = parse("早餐50現金\n午餐80現金", context_date=taipei_now)
        
        mock_enrichment = [
            {
                "id": "t1",
                "分類": "家庭/餐飲/早餐",
                "專案": "日常",
                "必要性": "必要日常支出",
                "明細說明": "",
            },
            {
                "id": "t2",
                "分類": "家庭/餐飲/午餐",
                "專案": "日常",
                "必要性": "必要日常支出",
                "明細說明": "",
            },
        ]
        
        result = enrich(envelope, mock_enrichment=mock_enrichment)
        
        assert len(result.transactions) == 2
        assert result.transactions[0].分類 == "家庭/餐飲/早餐"
        assert result.transactions[1].分類 == "家庭/餐飲/午餐"
        assert result.transactions[0].amount == 50.0
        assert result.transactions[1].amount == 80.0
