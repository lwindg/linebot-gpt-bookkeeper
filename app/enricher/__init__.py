# -*- coding: utf-8 -*-
"""
AI Enrichment Module (Phase 2)

負責對 Parser 輸出進行 AI Enrichment：
- 補充分類、專案、必要性、明細說明
- 驗證分類是否在允許清單內
- 權威欄位不可被 AI 修改
"""

from .enricher import enrich
from .types import EnrichedTransaction, EnrichedEnvelope

__all__ = [
    "enrich",
    "EnrichedTransaction",
    "EnrichedEnvelope",
]
