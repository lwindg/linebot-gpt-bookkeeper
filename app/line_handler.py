# -*- coding: utf-8 -*-
"""
LINE Message Handler Module

This module handles LINE message events and user interactions.
"""

import logging
from linebot.models import MessageEvent, TextSendMessage
from linebot import LineBotApi

from app.gpt_processor import process_multi_expense, MultiExpenseResult, BookkeepingEntry
from app.webhook_sender import send_multiple_webhooks

logger = logging.getLogger(__name__)


def format_confirmation_message(entry: BookkeepingEntry) -> str:
    """
    Format bookkeeping confirmation message (v1 單項目格式)

    Formats the bookkeeping entry data into a user-friendly confirmation message
    with all important details.

    Args:
        entry: BookkeepingEntry object

    Returns:
        str: Formatted confirmation message
    """
    # Calculate TWD amount
    twd_amount = entry.原幣金額 * entry.匯率

    message = f"""已成功記帳！

日期：{entry.日期}
品項：{entry.品項}
台幣金額：{twd_amount:.0f} TWD
付款方式：{entry.付款方式}
分類：{entry.分類}
必要性：{entry.必要性}
交易ID：{entry.交易ID}"""

    # Add optional detail note if present
    if entry.明細說明:
        message += f"\n明細說明：{entry.明細說明}"

    return message


def format_multi_confirmation_message(result: MultiExpenseResult, success_count: int, failure_count: int) -> str:
    """
    Format multi-item bookkeeping confirmation message (v1.5.0 新增)

    Formats multiple bookkeeping entries into a user-friendly confirmation message
    with all items listed.

    Args:
        result: MultiExpenseResult object containing all entries
        success_count: Number of successfully sent webhooks
        failure_count: Number of failed webhooks

    Returns:
        str: Formatted confirmation message
    """
    entries = result.entries
    total_items = len(entries)

    # 單項目：使用 v1 格式（向後相容）
    if total_items == 1:
        return format_confirmation_message(entries[0])

    # 多項目：使用 v1.5.0 新格式
    if success_count == total_items:
        message = f"✅ 記帳成功！已記錄 {total_items} 個項目：\n"
    elif failure_count == total_items:
        message = f"❌ 記帳失敗！{total_items} 個項目均未能記錄。\n"
    else:
        message = f"⚠️ 部分記帳成功！已記錄 {success_count}/{total_items} 個項目：\n"

    # 列出所有項目
    for idx, entry in enumerate(entries, start=1):
        twd_amount = entry.原幣金額 * entry.匯率

        message += f"\n📋 #{idx} {entry.品項}"
        message += f"\n💰 {twd_amount:.0f} 元 | {entry.付款方式}"
        message += f"\n📂 {entry.分類}"

        if entry.明細說明:
            message += f"\n📝 {entry.明細說明}"

        # 項目之間加空行（除了最後一個）
        if idx < total_items:
            message += "\n"

    # 顯示共用資訊
    if entries:
        message += f"\n\n🔖 交易ID：{entries[0].交易ID}"
        message += f"\n💳 付款方式：{entries[0].付款方式}（共用）"
        message += f"\n📅 日期：{entries[0].日期}"

    return message


def handle_text_message(event: MessageEvent, line_bot_api: LineBotApi) -> None:
    """
    Handle text message main flow (v1.5.0 更新：支援多項目支出)

    Flow:
    1. Receive user message
    2. Process via GPT (using process_multi_expense) to determine intent
    3. If multi_bookkeeping -> send multiple webhooks + return confirmation
    4. If conversation -> return GPT response
    5. If error -> return error message

    Args:
        event: LINE MessageEvent
        line_bot_api: LINE Bot API client
    """
    user_message = event.message.text
    reply_token = event.reply_token

    logger.info(f"Received message: {user_message}")

    try:
        # Process message via GPT (v1.5.0: using process_multi_expense)
        result = process_multi_expense(user_message)

        if result.intent == "multi_bookkeeping":
            # Multi-item or single-item bookkeeping
            entries = result.entries
            total_items = len(entries)

            logger.info(f"Processing {total_items} bookkeeping item(s)")

            # Send webhooks for all entries
            success_count, failure_count = send_multiple_webhooks(entries)

            # Generate confirmation message
            reply_text = format_multi_confirmation_message(result, success_count, failure_count)

        elif result.intent == "conversation":
            # Conversation: return GPT response
            reply_text = result.response_text if result.response_text else "您好！有什麼可以協助您的嗎？"
            logger.info(f"Conversation response: {reply_text}")

        elif result.intent == "error":
            # Error: return error message from GPT
            reply_text = result.error_message if result.error_message else "無法處理您的訊息，請檢查輸入格式。"
            logger.info(f"Error response: {reply_text}")

        else:
            reply_text = "無法理解您的訊息。"

        # Reply to LINE user
        logger.info(f"Sending reply to LINE: {reply_text[:100]}")
        line_bot_api.reply_message(
            reply_token,
            TextSendMessage(text=reply_text)
        )

        logger.info(f"Reply sent successfully")

    except Exception as e:
        # Unexpected error
        import traceback
        logger.error(f"Error handling message: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        line_bot_api.reply_message(
            reply_token,
            TextSendMessage(text="系統處理訊息時發生錯誤，請重試。")
        )
