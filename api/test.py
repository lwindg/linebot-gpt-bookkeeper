# -*- coding: utf-8 -*-
"""
Simple test endpoint for Vercel deployment debugging
"""

import os
from flask import Flask

app = Flask(__name__)

@app.route("/api/test", methods=['GET'])
def test():
    """Test endpoint that shows environment variable status"""

    env_status = {
        'LINE_CHANNEL_ACCESS_TOKEN': 'SET' if os.getenv('LINE_CHANNEL_ACCESS_TOKEN') else 'MISSING',
        'LINE_CHANNEL_SECRET': 'SET' if os.getenv('LINE_CHANNEL_SECRET') else 'MISSING',
        'OPENAI_API_KEY': 'SET' if os.getenv('OPENAI_API_KEY') else 'MISSING',
        'WEBHOOK_URL': 'SET' if os.getenv('WEBHOOK_URL') else 'NOT SET (OPTIONAL)',
    }

    response = "Vercel Test Endpoint\n\n"
    response += "Environment Variables:\n"
    for key, status in env_status.items():
        response += f"  {key}: {status}\n"

    return response, 200

if __name__ == "__main__":
    app.run(debug=True, port=5001)
