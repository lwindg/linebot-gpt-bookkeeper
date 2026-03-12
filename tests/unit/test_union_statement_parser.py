# -*- coding: utf-8 -*-

from app.services.statement_image_handler import parse_union_statement_ocr_text, _normalize_statement_date


def test_parse_union_statement_ocr_text_keeps_cashback_row() -> None:
    ocr = """
02/13 02/13 代扣－台水水費115/02-22642145007 TW 324
02/15 02/15 刷卡現金回饋－聯邦綠卡生活代扣繳回饋 -52
03/06 03/06 代扣－中華電信11502- 0911XXX862 TW 199
""".strip()

    lines = parse_union_statement_ocr_text(ocr)
    assert len(lines) == 3
    assert lines[1].description.startswith("刷卡現金回饋")
    assert lines[1].twd_amount == -52.0


def test_normalize_statement_date_uses_previous_year_for_cross_year_only() -> None:
    # Statement month is March 2026; February rows should remain in 2026.
    assert _normalize_statement_date("2026-03", "02/15") == "2026-02-15"
    # Statement month is January 2026; December rows belong to previous year.
    assert _normalize_statement_date("2026-01", "12/15") == "2025-12-15"
