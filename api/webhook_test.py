# -*- coding: utf-8 -*-
"""
Test webhook with LINE Bot SDK initialization
"""

import sys
import os
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging
from flask import Flask, request

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route("/api/webhook_test", methods=['GET'])
def test_init():
    """Test LINE Bot SDK initialization"""

    try:
        # Test 1: Import config
        from app.config import LINE_CHANNEL_ACCESS_TOKEN, LINE_CHANNEL_SECRET
        result = ["✅ Config imported"]

        # Test 2: Check values
        if LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET:
            result.append("✅ Tokens are set")
        else:
            result.append("❌ Tokens are empty")
            return "\n".join(result), 500

        # Test 3: Import LINE Bot SDK
        from linebot import LineBotApi, WebhookHandler
        result.append("✅ LINE Bot SDK imported")

        # Test 4: Initialize LineBotApi
        try:
            line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
            result.append(f"✅ LineBotApi initialized: {type(line_bot_api)}")
        except Exception as e:
            result.append(f"❌ LineBotApi failed: {e}")
            return "\n".join(result), 500

        # Test 5: Initialize WebhookHandler
        try:
            handler = WebhookHandler(LINE_CHANNEL_SECRET)
            result.append(f"✅ WebhookHandler initialized: {type(handler)}")
        except Exception as e:
            result.append(f"❌ WebhookHandler failed: {e}")
            return "\n".join(result), 500

        result.append("\n✅ All LINE Bot SDK initialization successful!")
        return "\n".join(result), 200

    except Exception as e:
        import traceback
        return f"❌ Error: {e}\n\n{traceback.format_exc()}", 500

if __name__ == "__main__":
    app.run(debug=True, port=5003)
