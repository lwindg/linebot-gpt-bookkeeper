# -*- coding: utf-8 -*-

from app.services.statement_image_handler import parse_fubon_statement_ocr_text


def test_parse_fubon_statement_ocr_text_basic_rows_and_skips():
    ocr = """
MASTER鈦金正卡末4碼8905
前期應繳總額 NTD 194
115/01/28 好市多EC 115/01/30 TWD 579
115/02/10 Uber Eats 115/02/11 TWD 1,051
115/02/13 VISA海外交易 115/02/14 TWD 300
115/02/12 合庫銀行 ATM跨行轉帳 115/02/12 TWD -194
""".strip()

    lines = parse_fubon_statement_ocr_text(ocr)

    # Skip header/summary lines; keep transaction-like rows.
    assert len(lines) == 4

    assert lines[0].card_hint == "富邦 Costco"
    assert lines[0].trans_date == "115/01/28"
    assert lines[0].post_date == "115/01/30"
    assert lines[0].description == "好市多EC"
    assert lines[0].currency == "TWD"
    assert lines[0].twd_amount == 579.0

    assert lines[1].twd_amount == 1051.0

    # Keep merchant rows that include VISA keyword (not card headers).
    assert lines[2].description == "VISA海外交易"
    assert lines[2].twd_amount == 300.0

    # Payment/transfer row should be normalized to positive (to match ledger 繳卡費)
    assert lines[3].twd_amount == 194.0
