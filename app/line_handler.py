# -*- coding: utf-8 -*-
"""
LINE Message Handler Module

This module handles LINE message events and user interactions.
"""

import logging
from linebot.models import MessageEvent, TextSendMessage
from linebot import LineBotApi
from linebot.v3.messaging import MessagingApiBlob

from app.gpt_processor import process_multi_expense
from app.services.webhook_sender import send_multiple_webhooks
from app.services.image_handler import (
    download_image,
    process_receipt_image,
    build_image_authoritative_envelope,
    ImageDownloadError,
    ImageTooLargeError,
    VisionAPIError,
)
from app.pipeline.image_flow import process_image_envelope
from app.line.formatters import (
    format_confirmation_message,
    format_multi_confirmation_message,
    format_cashflow_confirmation_message,
)
from app.line.update import handle_update_last_entry

logger = logging.getLogger(__name__)


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
    user_id = event.source.user_id  # 取得使用者 ID（用於 KV 儲存）

    logger.info(f"Received message from user {user_id}: {user_message}")

    try:
        # Process message via GPT (v1.5.0: using process_multi_expense)
        result = process_multi_expense(user_message)

        if result.intent in ("multi_bookkeeping", "cashflow_intents"):
            # Multi-item or single-item bookkeeping
            entries = result.entries
            total_items = len(entries)

            logger.info(f"Processing {total_items} bookkeeping item(s)")

            # Send webhooks for all entries (傳入 user_id 以儲存到 KV)
            success_count, failure_count = send_multiple_webhooks(entries, user_id)

            # Generate confirmation message
            reply_text = format_multi_confirmation_message(result, success_count, failure_count)

        elif result.intent == "update_last_entry":
            # 修改上一筆記帳（v1.10.0：使用 optimistic locking）
            logger.info(f"Update last entry request from user {user_id}")
            reply_text = handle_update_last_entry(user_id, result.fields_to_update, raw_message=user_message)

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


def handle_image_message(event: MessageEvent, messaging_api_blob: MessagingApiBlob, line_bot_api: LineBotApi) -> None:
    """
    處理圖片訊息的主流程（v1.5.0 新增）

    流程：
    1. 取得圖片訊息 ID
    2. 下載圖片內容
    3. 使用 Vision API 分析收據
    4. 若識別成功：
       - 轉換為 BookkeepingEntry 列表
       - 為每一筆發送 webhook
       - 回覆確認訊息（列出所有項目）
    5. 若識別失敗：
       - 回覆錯誤訊息並建議使用文字描述

    Args:
        event: LINE MessageEvent（圖片訊息）
        messaging_api_blob: LINE Messaging API Blob 實例（用於下載圖片）
        line_bot_api: LINE Bot API client（用於回覆訊息）

    錯誤處理：
        - 下載失敗 → 「圖片下載失敗，請稍後再試」
        - Vision API 失敗 → 「無法處理圖片，請改用文字描述」
        - 非台幣收據 → 「v1.5.0 僅支援台幣，請提供文字描述並換算台幣金額」
        - 非收據圖片 → 「無法辨識收據資訊，請提供文字描述」
        - 圖片模糊 → 「收據圖片不清晰，請提供文字描述：品項、金額、付款方式」
    """
    message_id = event.message.id
    reply_token = event.reply_token
    user_id = event.source.user_id  # 取得使用者 ID（用於 KV 儲存）

    logger.info(f"Received image message from user {user_id}, message_id={message_id}")

    try:
        # 1. 下載圖片
        logger.info("開始下載圖片")
        image_data = download_image(message_id, messaging_api_blob)
        logger.info(f"圖片下載成功，大小={len(image_data)} bytes")

        # 2. 使用 Vision API 分析收據
        logger.info("開始分析收據圖片")
        receipt_items, error_code, error_message = process_receipt_image(image_data)

        # 3. 檢查處理結果
        if error_code:
            # 識別失敗：根據錯誤碼回覆不同訊息
            if error_code == "not_receipt":
                reply_text = f"❌ 無法辨識收據資訊\n\n{error_message}\n\n💡 請提供文字描述進行記帳，格式如：\n「午餐花了150元，用現金」"
            elif error_code == "unclear":
                reply_text = f"❌ 收據圖片不清晰\n\n{error_message}\n\n💡 請提供文字描述，格式如：\n「品項、金額、付款方式」\n範例：「午餐花了150元，用現金」"
            elif error_code == "incomplete":
                reply_text = f"❌ 收據資訊不完整\n\n{error_message}\n\n💡 請提供文字描述補充完整資訊，格式如：\n「品項、金額、付款方式」"
            else:
                reply_text = f"❌ 無法處理收據圖片\n\n{error_message}\n\n💡 請改用文字描述進行記帳"

            logger.warning(f"收據識別失敗: {error_code} - {error_message}")

        else:
            # 識別成功：走 Parser-first image pipeline
            logger.info(f"收據識別成功，共 {len(receipt_items)} 個項目")

            image_envelope = build_image_authoritative_envelope(receipt_items)
            result = process_image_envelope(image_envelope)

            if result.intent in ("multi_bookkeeping", "cashflow_intents"):
                entries = result.entries
                total_items = len(entries)
                logger.info(f"轉換為 {total_items} 筆記帳項目")

                success_count, failure_count = send_multiple_webhooks(entries, user_id)
                reply_text = format_multi_confirmation_message(result, success_count, failure_count)

            elif result.intent == "error":
                reply_text = f"❌ 處理收據資料時發生錯誤\n\n{result.error_message}"
                logger.error(f"處理收據資料失敗: {result.error_message}")

            else:
                reply_text = "無法處理收據資料，請重試"

        # 回覆 LINE 使用者
        logger.info(f"回覆 LINE 訊息: {reply_text[:100]}")
        line_bot_api.reply_message(
            reply_token,
            TextSendMessage(text=reply_text)
        )

        logger.info("圖片訊息處理完成")

    except ImageTooLargeError as e:
        logger.error(f"圖片過大: {e}")
        reply_text = "❌ 圖片過大（超過 10MB）\n\n請重新上傳較小的圖片，或使用文字描述進行記帳"
        line_bot_api.reply_message(
            reply_token,
            TextSendMessage(text=reply_text)
        )

    except ImageDownloadError as e:
        logger.error(f"圖片下載失敗: {e}")
        reply_text = "❌ 圖片下載失敗\n\n請稍後再試，或使用文字描述進行記帳"
        line_bot_api.reply_message(
            reply_token,
            TextSendMessage(text=reply_text)
        )

    except VisionAPIError as e:
        logger.error(f"Vision API 失敗: {e}")
        reply_text = "❌ 無法處理圖片\n\n系統暫時無法分析收據，請使用文字描述進行記帳"
        line_bot_api.reply_message(
            reply_token,
            TextSendMessage(text=reply_text)
        )

    except Exception as e:
        # 未預期的錯誤
        import traceback
        logger.error(f"處理圖片訊息時發生錯誤: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        line_bot_api.reply_message(
            reply_token,
            TextSendMessage(text="系統處理圖片時發生錯誤，請重試或使用文字描述進行記帳。")
        )
