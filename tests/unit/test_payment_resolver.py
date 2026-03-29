# -*- coding: utf-8 -*-

from app.shared.payment_resolver import detect_payment_method, normalize_payment_method


def test_normalize_payment_method_supports_max_aliases_case_insensitive() -> None:
    assert normalize_payment_method("MAX") == "MAX"
    assert normalize_payment_method("maicoin") == "MAX"
    assert normalize_payment_method("MaiCoin") == "MAX"
    assert normalize_payment_method("Maicoin") == "MAX"


def test_normalize_payment_method_supports_bitcoin_aliases_case_insensitive() -> None:
    assert normalize_payment_method("比特幣") == "比特幣"
    assert normalize_payment_method("bitcoin") == "比特幣"
    assert normalize_payment_method("BTC") == "比特幣"
    assert normalize_payment_method("xbt") == "比特幣"


def test_detect_payment_method_supports_max_and_bitcoin_aliases() -> None:
    assert detect_payment_method("午餐 120 MAX") == "MAX"
    assert detect_payment_method("轉入 maicoin 2000") == "MAX"
    assert detect_payment_method("買幣 BTC 300") == "比特幣"
    assert detect_payment_method("定投 xbt 1000") == "比特幣"
