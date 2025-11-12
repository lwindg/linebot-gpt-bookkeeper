# -*- coding: utf-8 -*-
"""
LINE Message Handler Module

This module handles LINE message events and user interactions.
"""

import logging
from linebot.models import MessageEvent, TextSendMessage
from linebot import LineBotApi

from app.gpt_processor import process_message, BookkeepingEntry
from app.webhook_sender import send_to_webhook

logger = logging.getLogger(__name__)


def format_confirmation_message(entry: BookkeepingEntry) -> str:
    """
    Format bookkeeping confirmation message
    
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


def handle_text_message(event: MessageEvent, line_bot_api: LineBotApi) -> None:
    """
    Handle text message main flow
    
    Flow:
    1. Receive user message
    2. Process via GPT to determine intent
    3. If bookkeeping -> send to webhook + return confirmation
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
        # Process message via GPT
        entry = process_message(user_message)
        
        if entry.intent == "bookkeeping":
            # Send to webhook
            success = send_to_webhook(entry)
            
            if success:
                # Success: return confirmation message
                reply_text = format_confirmation_message(entry)
            else:
                # Failed: return error message
                reply_text = "記帳資料處理失敗，請稍後再試。"
        
        elif entry.intent == "conversation":
            # Conversation: return GPT response
            reply_text = entry.response_text
        
        else:
            reply_text = "無法理解您的訊息。"
        
        # Reply to LINE user
        line_bot_api.reply_message(
            reply_token,
            TextSendMessage(text=reply_text)
        )
        
        logger.info(f"Replied to user: {reply_text[:50]}...")
    
    except ValueError as e:
        # Validation error
        logger.error(f"Validation error: {e}")
        line_bot_api.reply_message(
            reply_token,
            TextSendMessage(text="無法處理您的訊息格式，請重試。")
        )
    
    except Exception as e:
        # Unexpected error
        logger.error(f"Error handling message: {e}")
        line_bot_api.reply_message(
            reply_token,
            TextSendMessage(text="系統處理訊息時發生錯誤，請重試。")
        )
