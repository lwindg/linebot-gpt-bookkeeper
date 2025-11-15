# -*- coding: utf-8 -*-
"""
KV Store Module (Vercel KV / Redis)

This module handles storing and retrieving last transaction data
for the "update last entry" feature.
"""

import logging
import json
from typing import Optional, Dict, Any
from redis import Redis
from app.config import KV_REST_API_URL, KV_REST_API_TOKEN, KV_ENABLED, LAST_TRANSACTION_TTL

logger = logging.getLogger(__name__)


def get_kv_client() -> Optional[Redis]:
    """
    取得 KV (Redis) 客戶端

    Returns:
        Redis 客戶端實例，若 KV 未啟用則回傳 None
    """
    if not KV_ENABLED:
        logger.warning("KV not enabled, skipping KV operations")
        return None

    try:
        # Vercel KV uses REST API via redis-py
        # URL format: rediss://default:token@host:port
        client = Redis.from_url(
            KV_REST_API_URL,
            password=KV_REST_API_TOKEN,
            decode_responses=True
        )
        return client
    except Exception as e:
        logger.error(f"Failed to create KV client: {e}")
        return None


def save_last_transaction(user_id: str, transaction_data: Dict[str, Any]) -> bool:
    """
    儲存使用者的最後一筆交易資料到 KV

    Args:
        user_id: LINE 使用者 ID
        transaction_data: 交易資料（包含交易ID、品項、金額、付款方式等）

    Returns:
        bool: 成功回傳 True，失敗回傳 False

    Example:
        >>> data = {
        ...     "交易ID": "20251115-143052",
        ...     "品項": "咖啡",
        ...     "原幣金額": 50,
        ...     "付款方式": "現金"
        ... }
        >>> save_last_transaction("U1234567890abcdef", data)
        True
    """
    if not KV_ENABLED:
        logger.info("KV not enabled, skipping save_last_transaction")
        return False

    client = get_kv_client()
    if not client:
        return False

    try:
        key = f"last_transaction:{user_id}"
        value = json.dumps(transaction_data, ensure_ascii=False)

        # 設定 TTL（預設 10 分鐘）
        client.setex(key, LAST_TRANSACTION_TTL, value)

        logger.info(f"Saved last transaction for user {user_id}: {transaction_data.get('交易ID')}")
        return True

    except Exception as e:
        logger.error(f"Failed to save last transaction for user {user_id}: {e}")
        return False


def get_last_transaction(user_id: str) -> Optional[Dict[str, Any]]:
    """
    取得使用者的最後一筆交易資料

    Args:
        user_id: LINE 使用者 ID

    Returns:
        交易資料 dict，若不存在或已過期則回傳 None

    Example:
        >>> get_last_transaction("U1234567890abcdef")
        {
            "交易ID": "20251115-143052",
            "品項": "咖啡",
            "原幣金額": 50,
            "付款方式": "現金"
        }
    """
    if not KV_ENABLED:
        logger.info("KV not enabled, skipping get_last_transaction")
        return None

    client = get_kv_client()
    if not client:
        return None

    try:
        key = f"last_transaction:{user_id}"
        value = client.get(key)

        if not value:
            logger.info(f"No last transaction found for user {user_id}")
            return None

        transaction_data = json.loads(value)
        logger.info(f"Retrieved last transaction for user {user_id}: {transaction_data.get('交易ID')}")
        return transaction_data

    except Exception as e:
        logger.error(f"Failed to get last transaction for user {user_id}: {e}")
        return None


def delete_last_transaction(user_id: str) -> bool:
    """
    刪除使用者的最後一筆交易資料（防止重複修改）

    Args:
        user_id: LINE 使用者 ID

    Returns:
        bool: 成功回傳 True，失敗回傳 False
    """
    if not KV_ENABLED:
        logger.info("KV not enabled, skipping delete_last_transaction")
        return False

    client = get_kv_client()
    if not client:
        return False

    try:
        key = f"last_transaction:{user_id}"
        client.delete(key)

        logger.info(f"Deleted last transaction for user {user_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to delete last transaction for user {user_id}: {e}")
        return False
