# -*- coding: utf-8 -*-

from app.services.statement_image_handler import parse_sinopac_statement_ocr_text


def test_parse_sinopac_statement_ocr_text_basic_rows_and_fx_fields():
    ocr = """
消費日 入帳起息日 卡號末四碼 帳單說明 臺幣金額 外幣折算日 外幣金額
02/05 02/05 永豐自扣已入帳，謝謝！ -23,003
01/18 01/22 8006 TF-桃園市龜山區南美國民小學 5,733
02/03 02/06 8006 OPENAI *CHATGPT SUBSCR OPENAI.COM US 663 02/03 USD21.000
02/03 02/06 8006 OPENAI *CHATGPT SUBSCR 國外交易服務費 10
02/02 02/02 8006 大戶消費回饋入帳戶—國內217元 0
""".strip()

    lines = parse_sinopac_statement_ocr_text(ocr)

    assert len(lines) == 5

    # Payment acknowledgment row has no last4, but should still be parsed as a valid statement line.
    assert lines[0].card_hint is None
    assert lines[0].description == "永豐自扣已入帳，謝謝！"
    assert lines[0].twd_amount == -23003.0

    assert lines[1].card_hint == "8006"
    assert lines[1].description == "TF-桃園市龜山區南美國民小學"
    assert lines[1].twd_amount == 5733.0

    # Foreign transaction row: keep fx_date/currency/foreign_amount
    assert lines[2].description == "OPENAI *CHATGPT SUBSCR OPENAI.COM US"
    assert lines[2].twd_amount == 663.0
    assert lines[2].fx_date == "02/03"
    assert lines[2].currency == "USD"
    assert lines[2].foreign_amount == 21.0
    assert lines[2].is_fee is False

    # Fee row
    assert lines[3].description == "OPENAI *CHATGPT SUBSCR 國外交易服務費"
    assert lines[3].is_fee is True
    assert lines[3].twd_amount == 10.0

    # Rebate row keeps 0 amount for later ignore logic
    assert lines[4].description == "大戶消費回饋入帳戶—國內217元"
    assert lines[4].twd_amount == 0.0
