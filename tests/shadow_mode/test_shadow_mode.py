# -*- coding: utf-8 -*-
"""
Shadow Mode Unit Tests (T028)

測試 Shadow Mode 的比對邏輯與記錄功能。
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.shadow_mode import (
    compare_entries,
    compare_results,
    log_comparison,
    FieldComparison,
    EntryComparison,
    ComparisonResult,
)
from app.gpt_processor import MultiExpenseResult, BookkeepingEntry


class TestFieldComparison:
    """測試欄位比對邏輯"""
    
    def test_matching_amounts(self):
        """金額相同應判定為一致"""
        gpt_entry = BookkeepingEntry(intent="bookkeeping", 原幣金額=100.0)
        parser_entry = BookkeepingEntry(intent="bookkeeping", 原幣金額=100.0)
        
        result = compare_entries(gpt_entry, parser_entry, 0)
        
        amount_field = next(f for f in result.fields if f.field_name == "原幣金額")
        assert amount_field.is_match is True
    
    def test_mismatching_amounts(self):
        """金額不同應判定為不一致"""
        gpt_entry = BookkeepingEntry(intent="bookkeeping", 原幣金額=100.0)
        parser_entry = BookkeepingEntry(intent="bookkeeping", 原幣金額=150.0)
        
        result = compare_entries(gpt_entry, parser_entry, 0)
        
        amount_field = next(f for f in result.fields if f.field_name == "原幣金額")
        assert amount_field.is_match is False
    
    def test_matching_payment_method(self):
        """付款方式相同應判定為一致"""
        gpt_entry = BookkeepingEntry(intent="bookkeeping", 付款方式="現金")
        parser_entry = BookkeepingEntry(intent="bookkeeping", 付款方式="現金")
        
        result = compare_entries(gpt_entry, parser_entry, 0)
        
        payment_field = next(f for f in result.fields if f.field_name == "付款方式")
        assert payment_field.is_match is True
    
    def test_none_vs_empty_string(self):
        """None 與空字串應視為相同"""
        gpt_entry = BookkeepingEntry(intent="bookkeeping", 收款支付對象=None)
        parser_entry = BookkeepingEntry(intent="bookkeeping", 收款支付對象="")
        
        result = compare_entries(gpt_entry, parser_entry, 0)
        
        counterparty_field = next(f for f in result.fields if f.field_name == "收款支付對象")
        assert counterparty_field.is_match is True


class TestCompareResults:
    """測試完整結果比對"""
    
    def test_consistent_single_entry(self):
        """單筆一致交易應判定為整體一致"""
        gpt_result = MultiExpenseResult(
            intent="multi_bookkeeping",
            entries=[BookkeepingEntry(intent="bookkeeping", 原幣金額=100.0, 付款方式="現金")]
        )
        parser_result = MultiExpenseResult(
            intent="multi_bookkeeping",
            entries=[BookkeepingEntry(intent="bookkeeping", 原幣金額=100.0, 付款方式="現金")]
        )
        
        comparison = compare_results(gpt_result, parser_result, "午餐100現金")
        
        assert comparison.is_consistent is True
        assert comparison.intent_match is True
        assert comparison.count_match is True
    
    def test_cashflow_multi_intent_compatible(self):
        """cashflow_intents 與 multi_bookkeeping 應視為相容"""
        gpt_result = MultiExpenseResult(
            intent="cashflow_intents",
            entries=[BookkeepingEntry(intent="bookkeeping", 原幣金額=5000.0)]
        )
        parser_result = MultiExpenseResult(
            intent="multi_bookkeeping",
            entries=[BookkeepingEntry(intent="bookkeeping", 原幣金額=5000.0)]
        )
        
        comparison = compare_results(gpt_result, parser_result, "提款5000")
        
        assert comparison.intent_match is True  # Should be compatible
    
    def test_entry_count_mismatch(self):
        """交易筆數不同應反映在 count_match"""
        gpt_result = MultiExpenseResult(
            intent="multi_bookkeeping",
            entries=[
                BookkeepingEntry(intent="bookkeeping", 原幣金額=80.0),
                BookkeepingEntry(intent="bookkeeping", 原幣金額=150.0),
            ]
        )
        parser_result = MultiExpenseResult(
            intent="multi_bookkeeping",
            entries=[BookkeepingEntry(intent="bookkeeping", 原幣金額=80.0)]
        )
        
        comparison = compare_results(gpt_result, parser_result, "早餐80 午餐150")
        
        assert comparison.count_match is False
        assert comparison.is_consistent is False
    
    def test_both_errors_is_consistent(self):
        """兩者都回傳 error 應視為一致"""
        gpt_result = MultiExpenseResult(intent="error", entries=[], error_message="GPT error")
        parser_result = MultiExpenseResult(intent="error", entries=[], error_message="Parser error")
        
        comparison = compare_results(gpt_result, parser_result, "invalid")
        
        assert comparison.is_consistent is True


class TestLogComparison:
    """測試記錄功能"""
    
    def test_log_creates_file(self, tmp_path):
        """應正確建立 log 檔案"""
        log_path = tmp_path / "shadow.jsonl"
        
        gpt_result = MultiExpenseResult(
            intent="multi_bookkeeping",
            entries=[BookkeepingEntry(intent="bookkeeping", 原幣金額=100.0)]
        )
        parser_result = MultiExpenseResult(
            intent="multi_bookkeeping",
            entries=[BookkeepingEntry(intent="bookkeeping", 原幣金額=100.0)]
        )
        
        comparison = compare_results(gpt_result, parser_result, "test message")
        log_comparison(comparison, str(log_path))
        
        assert log_path.exists()
        
        with open(log_path, "r", encoding="utf-8") as f:
            record = json.loads(f.readline())
        
        assert record["is_consistent"] is True
        assert record["user_message"] == "test message"
    
    def test_log_records_mismatches(self, tmp_path):
        """應正確記錄不一致的欄位"""
        log_path = tmp_path / "shadow.jsonl"
        
        gpt_result = MultiExpenseResult(
            intent="multi_bookkeeping",
            entries=[BookkeepingEntry(intent="bookkeeping", 原幣金額=100.0, 付款方式="現金")]
        )
        parser_result = MultiExpenseResult(
            intent="multi_bookkeeping",
            entries=[BookkeepingEntry(intent="bookkeeping", 原幣金額=100.0, 付款方式="Line Pay")]
        )
        
        comparison = compare_results(gpt_result, parser_result, "test")
        log_comparison(comparison, str(log_path))
        
        with open(log_path, "r", encoding="utf-8") as f:
            record = json.loads(f.readline())
        
        assert record["is_consistent"] is False
        assert len(record["mismatches"]) > 0
        assert any(m["field"] == "付款方式" for m in record["mismatches"])
