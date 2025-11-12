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
from linebot.models import MessageEvent, TextMessage

from app.config import LINE_CHANNEL_ACCESS_TOKEN, LINE_CHANNEL_SECRET
from app.line_handler import handle_text_message

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Initialize LINE Bot API client and Webhook Handler
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)


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


@handler.add(MessageEvent, message=TextMessage)
def message_text(event):
    """
    Handle text message events
    
    Called automatically when a text message event is received.
    Delegates actual processing to line_handler module.
    
    Args:
        event: LINE MessageEvent
    """
    try:
        handle_text_message(event, line_bot_api)
    except Exception as e:
        logger.error(f"Error in message_text handler: {e}")
        # Don't raise exception to prevent webhook failure


# Vercel Serverless Function entry point
# Vercel uses 'app' object as the handler
# Reference: https://vercel.com/docs/functions/serverless-functions/runtimes/python
def handler_vercel(request):
    """
    Vercel Serverless Function entry point (optional)
    
    Used by Vercel Python runtime if needed.
    """
    with app.test_request_context(
        path=request.path,
        method=request.method,
        headers=request.headers,
        data=request.get_data()
    ):
        return app.full_dispatch_request()


# Local development entry point
if __name__ == "__main__":
    app.run(debug=True, port=5000)
