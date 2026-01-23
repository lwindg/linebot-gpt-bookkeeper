# -*- coding: utf-8 -*-
"""
Shadow Mode Verification (Phase 4)

同時執行 GPT-first 與 Parser-first 路徑，比對輸出差異。
僅記錄後台 log，不影響 Line Bot 回應。
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from zoneinfo import ZoneInfo

from app.gpt_processor import MultiExpenseResult, BookkeepingEntry

logger = logging.getLogger(__name__)


@dataclass
class FieldComparison:
    """單一欄位比對結果"""
    field_name: str
    gpt_value: Any
    parser_value: Any
    is_match: bool


@dataclass
class EntryComparison:
    """單筆交易比對結果"""
    index: int
    fields: List[FieldComparison] = field(default_factory=list)
    
    @property
    def is_match(self) -> bool:
        return all(f.is_match for f in self.fields)
    
    @property
    def mismatched_fields(self) -> List[str]:
        return [f.field_name for f in self.fields if not f.is_match]


@dataclass
class ComparisonResult:
    """完整比對結果"""
    user_message: str
    timestamp: str
    gpt_intent: str
    parser_intent: str
    gpt_entry_count: int
    parser_entry_count: int
    entry_comparisons: List[EntryComparison] = field(default_factory=list)
    gpt_error: Optional[str] = None
    parser_error: Optional[str] = None
    
    @property
    def intent_match(self) -> bool:
        # cashflow_intents 和 multi_bookkeeping 視為相容
        compatible = {"cashflow_intents", "multi_bookkeeping"}
        if self.gpt_intent in compatible and self.parser_intent in compatible:
            return True
        return self.gpt_intent == self.parser_intent
    
    @property
    def count_match(self) -> bool:
        return self.gpt_entry_count == self.parser_entry_count
    
    @property
    def all_entries_match(self) -> bool:
        return all(e.is_match for e in self.entry_comparisons)
    
    @property
    def is_consistent(self) -> bool:
        """整體一致性判斷"""
        if self.gpt_error or self.parser_error:
            # 兩者都錯誤視為一致
            return bool(self.gpt_error and self.parser_error)
        return self.intent_match and self.count_match and self.all_entries_match


# 比對欄位清單（權威欄位優先）
COMPARISON_FIELDS = [
    "原幣金額",
    "付款方式", 
    "品項",
    "交易類型",
    "代墊狀態",
    "收款支付對象",
    "分類",
    "專案",
]


def compare_entries(
    gpt_entry: BookkeepingEntry,
    parser_entry: BookkeepingEntry,
    index: int
) -> EntryComparison:
    """比對兩筆交易的關鍵欄位"""
    comparisons = []
    
    for field_name in COMPARISON_FIELDS:
        gpt_val = getattr(gpt_entry, field_name, None)
        parser_val = getattr(parser_entry, field_name, None)
        
        # 正規化比對（處理 None vs 空字串）
        gpt_normalized = gpt_val if gpt_val else ""
        parser_normalized = parser_val if parser_val else ""
        
        # 金額使用數值比對
        if field_name == "原幣金額":
            try:
                is_match = float(gpt_normalized or 0) == float(parser_normalized or 0)
            except (ValueError, TypeError):
                is_match = str(gpt_normalized) == str(parser_normalized)
        else:
            is_match = str(gpt_normalized) == str(parser_normalized)
        
        comparisons.append(FieldComparison(
            field_name=field_name,
            gpt_value=gpt_val,
            parser_value=parser_val,
            is_match=is_match
        ))
    
    return EntryComparison(index=index, fields=comparisons)


def compare_results(
    gpt_result: MultiExpenseResult,
    parser_result: MultiExpenseResult,
    user_message: str
) -> ComparisonResult:
    """比對 GPT-first 與 Parser-first 的完整結果"""
    taipei_tz = ZoneInfo("Asia/Taipei")
    timestamp = datetime.now(taipei_tz).isoformat()
    
    # 檢查錯誤狀態
    gpt_error = gpt_result.error_message if gpt_result.intent == "error" else None
    parser_error = parser_result.error_message if parser_result.intent == "error" else None
    
    comparison = ComparisonResult(
        user_message=user_message,
        timestamp=timestamp,
        gpt_intent=gpt_result.intent,
        parser_intent=parser_result.intent,
        gpt_entry_count=len(gpt_result.entries),
        parser_entry_count=len(parser_result.entries),
        gpt_error=gpt_error,
        parser_error=parser_error,
    )
    
    # 逐筆比對（以較少的為準）
    min_count = min(len(gpt_result.entries), len(parser_result.entries))
    for i in range(min_count):
        entry_cmp = compare_entries(gpt_result.entries[i], parser_result.entries[i], i)
        comparison.entry_comparisons.append(entry_cmp)
    
    return comparison


def log_comparison(
    comparison: ComparisonResult,
    log_path: Optional[str] = None
) -> None:
    """記錄比對結果到 JSONL 檔案（I/O 失敗不中斷主流程）"""
    try:
        from app.config import SHADOW_LOG_PATH
        
        path = Path(log_path or SHADOW_LOG_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # 轉換為可序列化格式
        record = {
            "user_message": comparison.user_message,
            "timestamp": comparison.timestamp,
            "gpt_intent": comparison.gpt_intent,
            "parser_intent": comparison.parser_intent,
            "gpt_entry_count": comparison.gpt_entry_count,
            "parser_entry_count": comparison.parser_entry_count,
            "is_consistent": comparison.is_consistent,
            "gpt_error": comparison.gpt_error,
            "parser_error": comparison.parser_error,
            "mismatches": [],
        }
        
        # 記錄不一致的欄位
        for entry_cmp in comparison.entry_comparisons:
            if not entry_cmp.is_match:
                for fc in entry_cmp.fields:
                    if not fc.is_match:
                        record["mismatches"].append({
                            "entry_index": entry_cmp.index,
                            "field": fc.field_name,
                            "gpt": fc.gpt_value,
                            "parser": fc.parser_value,
                        })
        
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        
        logger.info(f"Shadow comparison logged: consistent={comparison.is_consistent}")
    
    except Exception as e:
        # I/O 失敗降級為警告，不中斷主流程
        logger.warning(f"Shadow Mode log failed (non-critical): {e}")


def run_shadow_mode(user_message: str) -> MultiExpenseResult:
    """
    執行 Shadow Mode：同時執行兩條路徑並比對。
    
    Returns:
        MultiExpenseResult: GPT-first 結果（作為主要回應）
    """
    from app.config import SHADOW_MODE_ENABLED
    
    if not SHADOW_MODE_ENABLED:
        # Shadow Mode 未啟用，直接執行一般流程
        from app.gpt_processor import process_multi_expense
        return process_multi_expense(user_message)
    
    # 執行 GPT-first（強制使用舊路徑）
    from app.gpt_processor import process_multi_expense_gpt_only
    gpt_result = process_multi_expense_gpt_only(user_message)
    
    # 執行 Parser-first
    from app.processor import process_with_parser
    try:
        parser_result = process_with_parser(user_message)
    except Exception as e:
        logger.error(f"Parser-first failed in shadow mode: {e}")
        parser_result = MultiExpenseResult(
            intent="error",
            entries=[],
            error_message=str(e),
        )
    
    # 比對並記錄
    comparison = compare_results(gpt_result, parser_result, user_message)
    log_comparison(comparison)
    
    # 回傳 GPT 結果（尚未切換主路徑）
    return gpt_result
