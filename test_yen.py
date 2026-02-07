# -*- coding: utf-8 -*-
import sys
import os

# 將專案目錄加入 path
sys.path.append(os.getcwd())

from app.parser.extract_amount import extract_amount_and_currency

test_cases = [
    ("拉麵 ¥1500", 1500.0, "JPY"),
    ("拉麵1500円", 1500.0, "JPY"),
    ("日元 2000 交通", 2000.0, "JPY"),
    ("午餐 120 現金", 120.0, "TWD"),
]

print("--- 測試日圓識別功能 ---")
for text, exp_amount, exp_currency in test_cases:
    amount, currency, remaining = extract_amount_and_currency(text)
    status = "✅" if (amount == exp_amount and currency == exp_currency) else "❌"
    print(f"{status} 輸入: {text} -> 金額: {amount}, 幣別: {currency}, 剩餘: {remaining}")
