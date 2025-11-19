# -*- coding: utf-8 -*-
"""
Vercel Serverless Function - LINE Bot Webhook Entry Point

This module handles:
1. Receive Webhook POST requests from LINE Platform
2. Validate X-Line-Signature
3. Process LINE events and handle messages
4. Return 200 OK to LINE (required for webhook acknowledgment)
"""

import sys
import os
from pathlib import Path

# Add project root to sys.path for local development
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, ImageMessage
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    MessagingApiBlob
)

from app.config import LINE_CHANNEL_ACCESS_TOKEN, LINE_CHANNEL_SECRET
from app.line_handler import handle_text_message, handle_image_message

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Global variables for lazy initialization (Vercel serverless requirement)
_line_bot_api = None
_messaging_api_blob = None
_handler = None
_handler_registered = False


def get_line_bot_api():
    """Get or initialize LINE Bot API client (lazy initialization)"""
    global _line_bot_api
    if _line_bot_api is None:
        logger.info("Initializing LineBotApi")
        _line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
    return _line_bot_api


def get_messaging_api_blob():
    """Get or initialize LINE Messaging API Blob client (lazy initialization for v1.5.0)"""
    global _messaging_api_blob
    if _messaging_api_blob is None:
        logger.info("Initializing MessagingApiBlob")
        configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
        api_client = ApiClient(configuration)
        _messaging_api_blob = MessagingApiBlob(api_client)
    return _messaging_api_blob


def get_handler():
    """Get or initialize Webhook Handler (lazy initialization)"""
    global _handler, _handler_registered
    if _handler is None:
        logger.info("Initializing WebhookHandler")
        _handler = WebhookHandler(LINE_CHANNEL_SECRET)

        # Register event handlers
        if not _handler_registered:
            @_handler.add(MessageEvent, message=TextMessage)
            def message_text(event):
                """Handle text message events"""
                try:
                    handle_text_message(event, get_line_bot_api())
                except Exception as e:
                    logger.error(f"Error in message_text handler: {e}")

            @_handler.add(MessageEvent, message=ImageMessage)
            def message_image(event):
                """Handle image message events (v1.5.0 新增)"""
                try:
                    handle_image_message(event, get_messaging_api_blob(), get_line_bot_api())
                except Exception as e:
                    logger.error(f"Error in message_image handler: {e}")

            _handler_registered = True
            logger.info("Event handlers registered (text + image)")

    return _handler


@app.route("/api/webhook", methods=['GET'])
def webhook_health():
    """Health check endpoint for GET requests"""
    return 'LINE Bot is running!', 200


@app.route("/api/webhook", methods=['POST'])
def webhook():
    """
    LINE Webhook entry function

    Handles POST requests from LINE Platform.
    Validates signature and delegates to handler for processing.

    Returns:
        str: Always returns 'OK' to acknowledge receipt to LINE
    """
    # Get signature
    signature = request.headers.get('X-Line-Signature')
    if not signature:
        logger.warning("Missing X-Line-Signature header")
        abort(400)

    # Get request body
    body = request.get_data(as_text=True)
    logger.info(f"Request body: {body}")

    # Get handler (lazy initialization)
    handler = get_handler()

    # Validate signature and handle events
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error("Invalid signature")
        abort(400)
    except Exception as e:
        # Even on error, return 200 to prevent LINE from retrying
        logger.error(f"Error handling webhook: {e}")

    return 'OK'


# Local development entry point
if __name__ == "__main__":
    app.run(debug=True, port=5000)
