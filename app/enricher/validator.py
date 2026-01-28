# -*- coding: utf-8 -*-
"""
Validation helpers for enrichment results.
"""

import logging

from app.shared.category_resolver import allowed_categories

logger = logging.getLogger(__name__)


def validate_category(category: str) -> str:
    """
    驗證分類是否在允許清單內。

    若不在清單內，嘗試找最接近的分類，
    若仍無匹配則回傳 "未分類"。
    """
    if not category or not category.strip():
        logger.warning("Empty category received, using '未分類'")
        return "未分類"

    category = category.strip()
    categories = allowed_categories()

    if category in categories:
        return category

    for cat in categories:
        if category in cat or cat.endswith(category):
            logger.warning(f"Category '{category}' normalized to '{cat}'")
            return cat

    logger.warning(f"Unknown category '{category}', using '未分類'")
    return "未分類"
