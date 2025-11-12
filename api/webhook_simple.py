# -*- coding: utf-8 -*-
"""
Simplified webhook to isolate the issue
"""

import sys
import os
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage

from app.config import LINE_CHANNEL_ACCESS_TOKEN, LINE_CHANNEL_SECRET
from app.line_handler import handle_text_message

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Initialize LINE Bot API - at module level like original
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)


@app.route("/api/webhook_simple", methods=['GET'])
def health():
    """Health check"""
    return 'Simple webhook is running!', 200


@app.route("/api/webhook_simple", methods=['POST'])
def webhook():
    """Webhook handler"""
    signature = request.headers.get('X-Line-Signature')
    if not signature:
        logger.warning("Missing X-Line-Signature")
        abort(400)

    body = request.get_data(as_text=True)
    logger.info(f"Request body: {body}")

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error("Invalid signature")
        abort(400)
    except Exception as e:
        logger.error(f"Error: {e}")

    return 'OK'


@handler.add(MessageEvent, message=TextMessage)
def message_text(event):
    """Handle text message"""
    try:
        handle_text_message(event, line_bot_api)
    except Exception as e:
        logger.error(f"Error in handler: {e}")


if __name__ == "__main__":
    app.run(debug=True, port=5004)
