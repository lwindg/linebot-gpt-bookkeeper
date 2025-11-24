# -*- coding: utf-8 -*-
"""
Webhook Sender Module

This module sends bookkeeping data to Make.com webhook.
"""

import requests
import logging
import time
from typing import List, Tuple, Optional
from app.config import WEBHOOK_URL, WEBHOOK_TIMEOUT
from app.gpt_processor import BookkeepingEntry
from app.kv_store import save_last_transaction

logger = logging.getLogger(__name__)


def send_to_webhook(entry: BookkeepingEntry, user_id: Optional[str] = None) -> bool:
    """
    Send bookkeeping data to Make.com webhook

    Converts BookkeepingEntry to JSON format expected by Make.com
    and sends via POST request to webhook URL.

    Args:
        entry: BookkeepingEntry object
        user_id: LINE user ID (optional, for saving to KV)

    Returns:
        bool: True if success, False if failed

    Error handling:
        - Network errors: returns False
        - HTTP 4xx/5xx: returns False
        - Timeout (default 10s): returns False
    """
    # Check if webhook URL is configured
    if not WEBHOOK_URL:
        logger.warning("WEBHOOK_URL not configured, skipping webhook send")
        return True

    # Prepare payload for Make.com (using Chinese field names as per spec)
    payload = {
        "operation": "CREATE",  # v1.5.0: 用於 Make.com Router 區分操作類型
        "日期": entry.日期,
        "品項": entry.品項,
        "原幣別": entry.原幣別,
        "原幣金額": entry.原幣金額,
        "匯率": entry.匯率,
        "付款方式": entry.付款方式,
        "交易ID": entry.交易ID,
        "明細說明": entry.明細說明,
        "分類": entry.分類,
        "專案": entry.專案,
        "必要性": entry.必要性,
        "代墊狀態": entry.代墊狀態,
        "收款支付對象": entry.收款支付對象,
        "附註": entry.附註,
    }
    
    try:
        logger.info(f"Sending webhook for transaction {entry.交易ID}")
        
        response = requests.post(
            WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=WEBHOOK_TIMEOUT
        )
        
        if response.status_code in [200, 201, 202]:
            logger.info(f"Webhook sent successfully: {entry.交易ID}")

            # 儲存最後一筆交易到 KV（用於「修改上一筆」功能）
            if user_id:
                transaction_data = {
                    "交易ID": entry.交易ID,
                    "品項": entry.品項,
                    "原幣金額": entry.原幣金額,
                    "付款方式": entry.付款方式,
                    "分類": entry.分類,
                    "日期": entry.日期,
                }
                save_last_transaction(user_id, transaction_data)

            return True
        else:
            logger.error(f"Webhook failed with status {response.status_code}: {response.text}")
            return False
    
    except requests.Timeout:
        logger.error(f"Webhook request timeout for transaction {entry.交易ID}")
        return False
    
    except requests.RequestException as e:
        logger.error(f"Webhook request failed for transaction {entry.交易ID}: {e}")
        return False
    
    except Exception as e:
        logger.error(f"Unexpected error sending webhook: {e}")
        return False


def send_multiple_webhooks(entries: List[BookkeepingEntry], user_id: Optional[str] = None, delay_seconds: float = 0.5) -> Tuple[int, int]:
    """
    為多個項目發送 webhook（v1.5.0 新功能）

    依序為每個 entry 呼叫 send_to_webhook()，記錄成功/失敗數量。
    即使部分失敗，仍繼續處理剩餘項目。

    **v1.8.1 改進**：加入延遲機制以避免後端並發寫入衝突（HTTP 409 Conflict）

    Args:
        entries: BookkeepingEntry 列表（共用交易ID）
        user_id: LINE user ID (optional, for saving to KV)
        delay_seconds: 每筆 webhook 之間的延遲秒數（預設 0.5 秒）

    Returns:
        Tuple[int, int]: (成功數量, 失敗數量)

    Examples:
        >>> entries = [entry1, entry2, entry3]
        >>> success, failure = send_multiple_webhooks(entries)
        >>> success
        3
        >>> failure
        0

    Note:
        延遲機制可避免 Google Sheets 等後端系統的並發寫入衝突。
        例如：4 筆記錄耗時約 2 秒（含 0.5s 延遲），但能確保全部成功寫入。
    """
    success_count = 0
    failure_count = 0

    logger.info(f"Sending {len(entries)} webhooks for multi-item transaction (delay={delay_seconds}s)")

    for idx, entry in enumerate(entries, start=1):
        logger.info(f"Sending webhook {idx}/{len(entries)}: {entry.品項} - {entry.原幣金額} TWD")

        # 只儲存第一筆到 KV（代表整個多項目交易）
        user_id_for_kv = user_id if idx == 1 else None

        if send_to_webhook(entry, user_id_for_kv):
            success_count += 1
            logger.info(f"Webhook {idx}/{len(entries)} sent successfully")
        else:
            failure_count += 1
            logger.error(f"Webhook {idx}/{len(entries)} failed")

        # 在非最後一筆時加入延遲，避免後端並發寫入衝突
        if idx < len(entries):
            logger.debug(f"Waiting {delay_seconds}s before next webhook...")
            time.sleep(delay_seconds)

    logger.info(f"Multi-webhook batch complete: {success_count} success, {failure_count} failure")

    return (success_count, failure_count)


def send_update_webhook(user_id: str, transaction_id: str, fields_to_update: dict) -> bool:
    """
    發送 UPDATE webhook 到 Make.com（v1.5.0 新功能）

    用於「修改上一筆」功能，發送 UPDATE 操作到 Make.com Router。

    Args:
        user_id: LINE 使用者 ID
        transaction_id: 要更新的交易 ID
        fields_to_update: 要更新的欄位（dict）

    Returns:
        bool: 成功回傳 True，失敗回傳 False

    Example:
        >>> send_update_webhook("U1234567890abcdef", "20251115-143052", {"付款方式": "Line 轉帳"})
        True
    """
    # Check if webhook URL is configured
    if not WEBHOOK_URL:
        logger.warning("WEBHOOK_URL not configured, skipping update webhook")
        return True

    # Prepare UPDATE payload
    payload = {
        "operation": "UPDATE",
        "user_id": user_id,
        "transaction_id": transaction_id,
        "fields_to_update": fields_to_update
    }

    try:
        logger.info(f"Sending UPDATE webhook for transaction {transaction_id}")
        logger.info(f"Fields to update: {fields_to_update}")

        response = requests.post(
            WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=WEBHOOK_TIMEOUT
        )

        if response.status_code in [200, 201, 202]:
            logger.info(f"UPDATE webhook sent successfully: {transaction_id}")
            return True
        else:
            logger.error(f"UPDATE webhook failed with status {response.status_code}: {response.text}")
            return False

    except requests.Timeout:
        logger.error(f"UPDATE webhook request timeout for transaction {transaction_id}")
        return False

    except requests.RequestException as e:
        logger.error(f"UPDATE webhook request failed for transaction {transaction_id}: {e}")
        return False

    except Exception as e:
        logger.error(f"Unexpected error sending UPDATE webhook: {e}")
        return False
