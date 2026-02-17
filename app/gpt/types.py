from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class BookkeepingEntry:
    intent: str
    日期: Optional[str] = None
    時間: Optional[str] = None
    品項: Optional[str] = None
    原幣別: Optional[str] = "TWD"
    原幣金額: Optional[float] = None
    匯率: Optional[float] = 1.0
    付款方式: Optional[str] = None
    手續費: Optional[float] = 0.0
    交易ID: Optional[str] = None
    明細說明: Optional[str] = ""
    分類: Optional[str] = None
    交易類型: Optional[str] = "支出"
    專案: Optional[str] = "日常"
    必要性: Optional[str] = None
    代墊狀態: Optional[str] = "無"
    收款支付對象: Optional[str] = ""
    附註: Optional[str] = ""
    response_text: Optional[str] = None  # For conversation intent


@dataclass
class MultiExpenseResult:
    intent: str
    entries: List[BookkeepingEntry] = field(default_factory=list)
    response_text: Optional[str] = None
    error_message: Optional[str] = None
    error_reason: Optional[str] = None
    fields_to_update: Optional[dict] = None
