# -*- coding: utf-8 -*-
"""
Webhook Sender Module

This module sends bookkeeping data to Make.com webhook.
"""

import requests
import logging
from typing import List, Tuple
from app.config import WEBHOOK_URL, WEBHOOK_TIMEOUT
from app.gpt_processor import BookkeepingEntry

logger = logging.getLogger(__name__)


def send_to_webhook(entry: BookkeepingEntry) -> bool:
    """
    Send bookkeeping data to Make.com webhook

    Converts BookkeepingEntry to JSON format expected by Make.com
    and sends via POST request to webhook URL.

    Args:
        entry: BookkeepingEntry object

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


def send_multiple_webhooks(entries: List[BookkeepingEntry]) -> Tuple[int, int]:
    """
    為多個項目發送 webhook（v1.5.0 新功能）

    依序為每個 entry 呼叫 send_to_webhook()，記錄成功/失敗數量。
    即使部分失敗，仍繼續處理剩餘項目。

    Args:
        entries: BookkeepingEntry 列表（共用交易ID）

    Returns:
        Tuple[int, int]: (成功數量, 失敗數量)

    Examples:
        >>> entries = [entry1, entry2, entry3]
        >>> success, failure = send_multiple_webhooks(entries)
        >>> success
        3
        >>> failure
        0
    """
    success_count = 0
    failure_count = 0

    logger.info(f"Sending {len(entries)} webhooks for multi-item transaction")

    for idx, entry in enumerate(entries, start=1):
        logger.info(f"Sending webhook {idx}/{len(entries)}: {entry.品項} - {entry.原幣金額} TWD")

        if send_to_webhook(entry):
            success_count += 1
            logger.info(f"Webhook {idx}/{len(entries)} sent successfully")
        else:
            failure_count += 1
            logger.error(f"Webhook {idx}/{len(entries)} failed")

    logger.info(f"Multi-webhook batch complete: {success_count} success, {failure_count} failure")

    return (success_count, failure_count)
