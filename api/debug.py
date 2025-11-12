# -*- coding: utf-8 -*-
"""
Debug endpoint to test module imports step by step
"""

from flask import Flask
import sys
import traceback

app = Flask(__name__)

@app.route("/api/debug", methods=['GET'])
def debug():
    """Test imports step by step"""

    results = []
    results.append("=== Import Test ===\n")

    # Test 1: Basic imports
    try:
        import os
        results.append("✅ os")
    except Exception as e:
        results.append(f"❌ os: {e}")

    # Test 2: dotenv
    try:
        from dotenv import load_dotenv
        results.append("✅ dotenv")
    except Exception as e:
        results.append(f"❌ dotenv: {e}")

    # Test 3: requests
    try:
        import requests
        results.append("✅ requests")
    except Exception as e:
        results.append(f"❌ requests: {e}")

    # Test 4: OpenAI
    try:
        from openai import OpenAI
        results.append("✅ openai")
    except Exception as e:
        results.append(f"❌ openai: {e}")

    # Test 5: LINE Bot SDK
    try:
        from linebot import LineBotApi, WebhookHandler
        results.append("✅ linebot (LineBotApi, WebhookHandler)")
    except Exception as e:
        results.append(f"❌ linebot: {e}")

    # Test 6: LINE models
    try:
        from linebot.models import MessageEvent, TextMessage
        results.append("✅ linebot.models")
    except Exception as e:
        results.append(f"❌ linebot.models: {e}")

    # Test 7: app.config
    try:
        sys.path.insert(0, '/var/task')
        from app.config import LINE_CHANNEL_ACCESS_TOKEN
        results.append("✅ app.config")
    except Exception as e:
        results.append(f"❌ app.config: {e}\n{traceback.format_exc()}")

    # Test 8: app.gpt_processor
    try:
        from app.gpt_processor import process_message
        results.append("✅ app.gpt_processor")
    except Exception as e:
        results.append(f"❌ app.gpt_processor: {e}\n{traceback.format_exc()}")

    # Test 9: app.line_handler
    try:
        from app.line_handler import handle_text_message
        results.append("✅ app.line_handler")
    except Exception as e:
        results.append(f"❌ app.line_handler: {e}\n{traceback.format_exc()}")

    return "\n".join(results), 200, {'Content-Type': 'text/plain; charset=utf-8'}

if __name__ == "__main__":
    app.run(debug=True, port=5002)
