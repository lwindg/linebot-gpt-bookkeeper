
import re
from typing import Tuple

# --- From extract_amount.py ---
_CURRENCY_SYMBOLS = r"\$|USD|JPY|EUR|CNY|TWD|¥|円"
_CURRENCY_WORDS = r"美金|美元|日幣|日圓|日元|歐元|人民幣|台幣"
_CURRENCY_ALL = rf"{_CURRENCY_SYMBOLS}|{_CURRENCY_WORDS}"
_AMOUNT_PATTERN = re.compile(
    rf"({_CURRENCY_ALL})?\s*(-?\d{{1,3}}(?:,\d{{3}})*|(?:\d+))(?:\.\d+)?\s*({_CURRENCY_ALL})?",
    re.IGNORECASE
)
_DATE_PATTERN = re.compile(
    r"(20\d{2}[/-]\d{1,2}[/-]\d{1,2}|"
    r"\d{3}[/-]\d{1,2}[/-]\d{1,2}|"
    r"\d{1,2}[/-]\d{1,2})"
)
_TIME_PATTERN = re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\b")

def test_extract(text):
    matches = list(_AMOUNT_PATTERN.finditer(text))
    date_matches = list(_DATE_PATTERN.finditer(text))
    time_matches = list(_TIME_PATTERN.finditer(text))
    
    exclude_spans = [m.span() for m in date_matches] + [m.span() for m in time_matches]
    def _overlaps(ms, me):
        for es, ee in exclude_spans:
            if (ms >= es and me <= ee) or (ms < ee and me > es): return True
        return False
    
    matches = [m for m in matches if not _overlaps(m.start(), m.end())]
    
    if not matches: return 0, "TWD"
    
    best_match = None
    for m in matches:
        if m.group(1) or m.group(3):
            best_match = m
            break
    if not best_match: best_match = matches[-1]
    
    amount_str = best_match.group(2).replace(",", "")
    full = best_match.group(0)
    dec = re.search(r"\.\d+", full)
    if dec: amount_str += dec.group(0)
    return float(amount_str), best_match.group(3) or best_match.group(1) or "TWD"

# --- From split_items.py ---
_SPLIT_PATTERN = re.compile(r"[\n,，;；、]+")
def test_split(text):
    normalized = re.sub(r"(\d),(\d{3})", r"\1\2", text)
    normalized = re.sub(r"(\d{1,5})[、,](\d{1,5})", r"\1@@\2", normalized)
    parts = _SPLIT_PATTERN.split(normalized)
    return [p.replace("@@", "、").strip() for p in parts if p.strip()]

# Test Cases
print("--- Image 1 Case ---")
msg1 = "2/14 17:44 淺草到成田機場 2、3航廈 1302日圓 suica"
split1 = test_split(msg1)
print(f"Split: {split1}")
for p in split1:
    print(f"  Extract from '{p}': {test_extract(p)}")

print("\n--- Image 2 Case ---")
msg2 = "合庫提款 26,000"
split2 = test_split(msg2)
print(f"Split: {split2}")
for p in split2:
    print(f"  Extract from '{p}': {test_extract(p)}")

print("\n--- Thousands and Decimals ---")
print(f"1,234.56 -> {test_extract('1,234.56')}")
print(f"10,000 -> {test_extract('10,000')}")

print("\n--- Normal Multi-items ---")
msg3 = "蘋果 100、香蕉 50"
split3 = test_split(msg3)
print(f"Split: {split3}")
