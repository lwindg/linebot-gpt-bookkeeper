#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shadow Mode Verification Script (T029)

執行 Shadow Mode 驗證，比對 GPT-first 與 Parser-first 結果。
測試優先序：單項目支出 -> 多項目支出 -> 現金流 -> 代墊/需支付

使用方式：
    python scripts/run_shadow_mode.py [--skip-gpt]
    
    --skip-gpt: Parser-first 使用 skip_gpt=True（不呼叫 GPT Enrichment）
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.shadow_mode import compare_results, log_comparison
from app.gpt_processor import process_multi_expense_gpt_only, MultiExpenseResult
from app.processor import process_with_parser


# 只比對的欄位
FOCUS_FIELDS = {"分類", "專案"}

# 顯示但不比對的欄位
DISPLAY_ONLY_FIELDS = {"品項"}

# 測試案例（按優先序排列）
TEST_CASES = [
    # === 單項目支出 ===
    ("午餐120現金", "單項目：基本中文"),
    ("早餐80元 Line Pay", "單項目：Line Pay"),
    ("咖啡55元大戶", "單項目：大戶卡"),
    ("麥當勞189狗卡", "單項目：狗卡"),
    
    # === 多項目支出 ===
    ("早餐80\n午餐150 現金", "多項目：換行分隔"),
    ("咖啡50、蛋糕80 Line Pay", "多項目：頓號分隔"),
    ("計程車200, 晚餐350 大戶", "多項目：逗號分隔"),
    
    # === 現金流 ===
    ("從richart提款5000", "現金流：提款"),
    ("轉帳給房東15000 合庫", "現金流：轉帳（待確認）"),
    ("薪水入帳50000", "現金流：收入"),
    
    # === 代墊/需支付 ===
    ("幫妹代墊午餐150現金", "代墊：幫X代墊"),
    ("代爸買藥品500合庫", "代墊：代X買"),
    ("阿姨先墊晚餐300", "需支付：X先墊"),
]


def run_verification(skip_gpt: bool = False):
    """執行 Shadow Mode 驗證"""
    print("=" * 60)
    print("Shadow Mode Verification")
    print(f"Parser-first skip_gpt: {skip_gpt}")
    print(f"Compare fields: {', '.join(sorted(FOCUS_FIELDS))} (items are listed only)")
    print("=" * 60)
    print()
    
    results = {
        "total": 0,
        "consistent": 0,
        "inconsistent": 0,
        "gpt_error": 0,
        "parser_error": 0,
        "details": [],
    }
    
    for message, description in TEST_CASES:
        print(f"📝 {description}")
        print(f"   輸入: {message}")
        
        # GPT-first
        try:
            gpt_result = process_multi_expense_gpt_only(message)
        except Exception as e:
            gpt_result = MultiExpenseResult(intent="error", entries=[], error_message=str(e))
            results["gpt_error"] += 1
        
        # Parser-first
        try:
            parser_result = process_with_parser(message, skip_gpt=skip_gpt)
        except Exception as e:
            parser_result = MultiExpenseResult(intent="error", entries=[], error_message=str(e))
            results["parser_error"] += 1
        
        # Compare
        comparison = compare_results(gpt_result, parser_result, message)
        # 在此腳本中只關注分類與專案（品項只列出不比對）
        for entry_cmp in comparison.entry_comparisons:
            entry_cmp.fields = [
                f for f in entry_cmp.fields if f.field_name in FOCUS_FIELDS
            ]
        log_comparison(comparison)
        
        results["total"] += 1
        if comparison.is_consistent:
            results["consistent"] += 1
            print(f"   ✅ 一致")
        else:
            results["inconsistent"] += 1
            print(f"   ❌ 不一致")
            
            # Show differences
            if not comparison.intent_match:
                print(f"      Intent: GPT={comparison.gpt_intent} vs Parser={comparison.parser_intent}")
            if not comparison.count_match:
                print(f"      Count: GPT={comparison.gpt_entry_count} vs Parser={comparison.parser_entry_count}")
            
            for entry_cmp in comparison.entry_comparisons:
                # 列出品項（僅顯示，不比對）
                try:
                    gpt_item = gpt_result.entries[entry_cmp.index].品項
                    parser_item = parser_result.entries[entry_cmp.index].品項
                    print(f"      [品項] GPT={gpt_item} vs Parser={parser_item}")
                except Exception:
                    pass
                for fc in entry_cmp.fields:
                    if not fc.is_match:
                        print(f"      [{entry_cmp.index}] {fc.field_name}: GPT={fc.gpt_value} vs Parser={fc.parser_value}")
        
        results["details"].append({
            "message": message,
            "description": description,
            "is_consistent": comparison.is_consistent,
        })
        print()
    
    # Summary
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    consistency_rate = results["consistent"] / results["total"] * 100 if results["total"] > 0 else 0
    print(f"總測試: {results['total']}")
    print(f"一致: {results['consistent']} ({consistency_rate:.1f}%)")
    print(f"不一致: {results['inconsistent']}")
    print(f"GPT 錯誤: {results['gpt_error']}")
    print(f"Parser 錯誤: {results['parser_error']}")
    print()
    
    if consistency_rate >= 90:
        print("🎉 一致率 ≥ 90%，驗證通過！")
    else:
        print("⚠️ 一致率 < 90%，需進一步分析差異。")
    
    return results


def main():
    parser = argparse.ArgumentParser(description="Run Shadow Mode verification")
    parser.add_argument("--skip-gpt", action="store_true", 
                        help="Use skip_gpt=True for Parser-first (no GPT enrichment)")
    args = parser.parse_args()
    
    run_verification(skip_gpt=args.skip_gpt)


if __name__ == "__main__":
    main()
