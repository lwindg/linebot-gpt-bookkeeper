# -*- coding: utf-8 -*-
"""
Item Splitting Logic (T013)

負責將多項目訊息切割為單一項目。
分隔符號：換行、逗號、分號、頓號。
"""

import re

# 分隔符號 Pattern
# 支援：換行(\n), 逗號(,), 全形逗號(，), 分號(;), 全形分號(；), 頓號(、)
# 注意：排除數字中的逗號 (e.g. 1,000) -> 需小心的 Regex
# 簡單策略：先用明顯的分隔符切割，再處理細節
_SPLIT_PATTERN = re.compile(r"[\n,，;；、]+")

def split_items(text: str) -> list[str]:
    """
    將訊息切割為多個項目。
    
    Args:
        text: 原始訊息
    
    Returns:
        list[str]: 切割後的項目列表
    """
    if not text:
        return []

    # 初步切割
    # 為了避免切斷 "1,000" 這種數字，我們可以使用 lookbehind/lookahead
    # 但為簡化與效能，假設輸入格式通常有空格或中文分隔
    # 若使用者輸入 "午餐1,000"，可能會被切成 "午餐1" "000" -> 風險
    # 策略：如果逗號前後都是數字，則不視為分隔符號
    
    # 1. 替換掉數字中間的逗號 (e.g., "1,200" -> "1200") 
    # 這也能幫助後續金額解析
    normalized = re.sub(r"(\d),(\d{3})", r"\1\2", text)
    
    # 2. 避免切斷數字列表 (e.g. "1、2月", "2、3 航廈")
    # 保護 "數字、數字" 與 "數字,數字" (不帶千分位的逗號)
    normalized = re.sub(r"(\d+)\s*[、,]\s*(\d+)", r"\1@@\2", normalized)

    # 3. 進行分割
    parts = _SPLIT_PATTERN.split(normalized)
    
    # 4. 過濾空字串與清理
    results = []
    for part in parts:
        clean_part = part.replace("@@", "、").strip()
        if clean_part:
            results.append(clean_part)
            
    return results
