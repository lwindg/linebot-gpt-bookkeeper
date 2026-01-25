# -*- coding: utf-8 -*-
"""
Parser Error Types (T015)

定義 Parser 解析錯誤類型與訊息模板。
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional


class ParserErrorCode(Enum):
    """Parser 錯誤代碼"""
    
    MISSING_AMOUNT = "missing_amount"           # 缺少金額
    MISSING_ITEM = "missing_item"               # 缺少品項
    INVALID_AMOUNT = "invalid_amount"           # 金額格式錯誤
    INVALID_PAYMENT_METHOD = "invalid_payment"  # 付款方式無法識別
    AMBIGUOUS_ADVANCE = "ambiguous_advance"     # 代墊狀態不明確
    MIXED_INTENT = "mixed_intent"               # 混合現金流與一般支出
    MIXED_PAYMENT_METHOD = "mixed_payment"      # 多項目付款方式不一致
    EMPTY_MESSAGE = "empty_message"             # 空訊息
    PARSE_FAILED = "parse_failed"               # 解析失敗（通用）


# 錯誤訊息模板
ERROR_MESSAGES = {
    ParserErrorCode.MISSING_AMOUNT: "請補上金額！例如：「午餐 80 現金」",
    ParserErrorCode.MISSING_ITEM: "請補上品項！例如：「午餐 80 現金」",
    ParserErrorCode.INVALID_AMOUNT: "金額格式有誤，請確認數字是否正確",
    ParserErrorCode.INVALID_PAYMENT_METHOD: "無法識別付款方式「{value}」，請使用：現金、Line Pay、狗卡、灰狗、合庫 等",
    ParserErrorCode.AMBIGUOUS_ADVANCE: "代墊狀態不明確，請說明是「代墊」還是「需支付」",
    ParserErrorCode.MIXED_INTENT: "請分開輸入：現金流（轉帳/繳卡費/提款）和一般支出不能混在同一句",
    ParserErrorCode.MIXED_PAYMENT_METHOD: "偵測到不同付款方式，請分開記帳或使用共用付款方式",
    ParserErrorCode.EMPTY_MESSAGE: "請輸入記帳內容",
    ParserErrorCode.PARSE_FAILED: "無法解析訊息，請確認格式是否正確",
}


@dataclass
class ParserError(Exception):
    """Parser 解析錯誤"""
    
    code: ParserErrorCode
    message: str
    details: Optional[dict] = None

    def __str__(self) -> str:
        return self.message

    @classmethod
    def from_code(cls, code: ParserErrorCode, **kwargs) -> "ParserError":
        """從錯誤代碼建立錯誤物件"""
        template = ERROR_MESSAGES.get(code, "解析錯誤")
        message = template.format(**kwargs) if kwargs else template
        return cls(code=code, message=message, details=kwargs if kwargs else None)
