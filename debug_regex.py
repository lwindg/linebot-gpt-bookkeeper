
import re

_CURRENCY_SYMBOLS = r"\$|USD|JPY|EUR|CNY|TWD|¥|円"
_CURRENCY_WORDS = r"美金|美元|日幣|日圓|日元|歐元|人民幣|台幣"
_CURRENCY_ALL = rf"{_CURRENCY_SYMBOLS}|{_CURRENCY_WORDS}"

# V3 Regex: 優先匹配長數字，並確保千分位與小數點完整
_AMOUNT_PATTERN = re.compile(
    rf"({_CURRENCY_ALL})?\s*(-?(?:\d{{1,3}}(?:,\d{{3}})+|\d+))(?:\.\d+)?\s*({_CURRENCY_ALL})?",
    re.IGNORECASE
)

def debug_extract(text):
    print(f"Testing: [{text}]")
    matches = list(_AMOUNT_PATTERN.finditer(text))
    for i, m in enumerate(matches):
        print(f"  Match {i}: '{m.group(0)}' (G1:{m.group(1)}, G2:{m.group(2)}, G3:{m.group(3)})")
    
    # Logic from extract_amount.py
    best_match = None
    for m in matches:
        if m.group(1) or m.group(3):
            best_match = m
            break
    if not best_match and matches:
        best_match = matches[-1]
    
    if best_match:
        amount_str = best_match.group(2).replace(",", "")
        # Find decimal point in the full match string if it exists
        full = best_match.group(0)
        dec = re.search(r"\.\d+", full)
        if dec: amount_str += dec.group(0)
        print(f"  RESULT: {amount_str}")
    else:
        print("  RESULT: None")

debug_extract("2/14 17:44 淺草到成田機場 2、3航廈 1302日圓 suica")
debug_extract("合庫提款 26,000")
debug_extract("1,234.56")
debug_extract("蘋果 100, 香蕉 50")
