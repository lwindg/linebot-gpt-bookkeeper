#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test webhook with correct LINE signature
"""

import hmac
import hashlib
import base64
import json
import requests
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.config import LINE_CHANNEL_SECRET

def generate_signature(body: str, channel_secret: str) -> str:
    """
    Generate LINE webhook signature

    Args:
        body: Request body as string
        channel_secret: LINE channel secret

    Returns:
        str: Base64 encoded signature
    """
    hash_obj = hmac.new(
        channel_secret.encode('utf-8'),
        body.encode('utf-8'),
        hashlib.sha256
    )
    signature = base64.b64encode(hash_obj.digest()).decode('utf-8')
    return signature


def test_local_webhook():
    """Test local webhook with correct signature"""

    # Read test payload
    with open('test_line_webhook.json', 'r') as f:
        payload = json.load(f)

    # Convert to string (must match exactly what will be sent)
    body = json.dumps(payload, separators=(',', ':'), ensure_ascii=False)

    # Generate signature
    signature = generate_signature(body, LINE_CHANNEL_SECRET)

    print(f"Payload:\n{body}\n")
    print(f"Signature: {signature}\n")

    # Send request to local server
    url = "http://127.0.0.1:5000/api/webhook"
    headers = {
        "Content-Type": "application/json",
        "X-Line-Signature": signature
    }

    try:
        response = requests.post(url, data=body.encode('utf-8'), headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")

        if response.status_code == 200:
            print("\n✅ Success!")
        else:
            print(f"\n❌ Failed with status {response.status_code}")

    except requests.exceptions.ConnectionError:
        print("❌ Connection failed. Is Flask server running?")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    test_local_webhook()
