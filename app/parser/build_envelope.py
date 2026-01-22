# -*- coding: utf-8 -*-
"""
Envelope Builder (T014)

負責組裝 AuthoritativeEnvelope。
"""

from datetime import datetime
from typing import List

# Avoid circular import at runtime by using strings or postponing imports if necessary
# But here we import types for type hinting
from app.parser.types import TransactionType
from app.parser import AuthoritativeEnvelope, Transaction

def build_envelope(
    source_text: str,
    transactions: List[Transaction],
    timestamp: datetime
) -> AuthoritativeEnvelope:
    """
    組裝權威 JSON Envelope。
    
    Args:
        source_text: 原始輸入文字
        transactions: 解析後的交易列表
        timestamp: 解析時間
    
    Returns:
        AuthoritativeEnvelope
    """
    return AuthoritativeEnvelope(
        source_text=source_text,
        parse_timestamp=timestamp.isoformat(),
        transactions=transactions,
        # constraints 由 dataclass default 處理
    )
