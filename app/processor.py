# -*- coding: utf-8 -*-
"""
Parser-first Processor (Phase 3)

新的 Parser-first 處理入口，使用 Parser + Enricher 架構。
"""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

from app.parser import parse, ParserError
from app.enricher import enrich, apply_exchange_rates, ExchangeRateUnavailableError
from app.converter import enriched_to_multi_result
from app.gpt.types import MultiExpenseResult, BookkeepingEntry
from app.shared.payment_resolver import detect_payment_method

logger = logging.getLogger(__name__)


def process_with_parser(
    user_message: str,
    *,
    skip_gpt: bool = False,
    user_id: Optional[str] = None,
) -> MultiExpenseResult:
    """
    Parser-first 處理流程。
    
    Args:
        user_message: 使用者訊息
        skip_gpt: 若為 True，跳過 GPT Enrichment（使用預設分類）
        user_id: 使用者 ID (用於讀取鎖定設定)
    
    Returns:
        MultiExpenseResult: 與舊版相容的結果格式
    
    流程：
    1. Parser: parse(message) -> AuthoritativeEnvelope
    2. Enricher: enrich(envelope) -> EnrichedEnvelope
    3. Converter: 轉換為 MultiExpenseResult（套用共用付款方式）
    """
    taipei_tz = ZoneInfo("Asia/Taipei")
    context_date = datetime.now(taipei_tz)
    
    # Normalize parser-first input to handle glued tokens like "$250現金".
    try:
        from app.parser.normalize_input import normalize_parser_input

        user_message = normalize_parser_input(user_message)
    except Exception:
        pass

    # 偵測整句的共用付款方式（如：午餐80, 晚餐150 現金）
    shared_payment = detect_payment_method(user_message)
    if shared_payment:
        logger.debug(f"Detected shared payment method: {shared_payment}")
    
    try:
        # Step 1: Parser
        envelope = parse(user_message, context_date=context_date)
        logger.info(f"Parser extracted {len(envelope.transactions)} transactions")
        
        # Step 2: Enricher
        enriched = enrich(envelope, skip_gpt=skip_gpt)
        apply_exchange_rates(enriched.transactions)
        logger.info(f"Enricher processed {len(enriched.transactions)} transactions")
        
        # Step 3: Convert to legacy format（套用共用付款方式）
        result = enriched_to_multi_result(enriched, shared_payment=shared_payment, user_id=user_id)
        return result
        
    except ParserError as e:
        # Parser 錯誤 -> 回傳 error intent
        logger.warning(f"Parser error: {e.message}")
        return MultiExpenseResult(
            intent="error",
            entries=[],
            error_message=e.message,
            error_reason=str(e.code),
        )
    except ExchangeRateUnavailableError as e:
        logger.warning(f"Exchange rate unavailable: {e.currency}")
        return MultiExpenseResult(
            intent="error",
            entries=[],
            error_message=str(e),
            error_reason="rate_unavailable",
        )
    except Exception as e:
        # 其他錯誤
        logger.error(f"Unexpected error in parser-first flow: {e}")
        return MultiExpenseResult(
            intent="error",
            entries=[],
            error_message=f"處理失敗：{str(e)}",
            error_reason="unexpected_error",
        )
