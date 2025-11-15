"""
Environment configuration module
Loads and validates all required environment variables.
"""

import os
from dotenv import load_dotenv

# Load .env file (for local development)
load_dotenv()

# Required environment variables
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Optional environment variables (with defaults)
WEBHOOK_URL = os.getenv('WEBHOOK_URL', '')
GPT_MODEL = os.getenv('GPT_MODEL', 'gpt-4o-mini')
GPT_VISION_MODEL = os.getenv('GPT_VISION_MODEL', 'gpt-4o')
WEBHOOK_TIMEOUT = int(os.getenv('WEBHOOK_TIMEOUT', '10'))

# Validate required variables
required_vars = {
    'LINE_CHANNEL_ACCESS_TOKEN': LINE_CHANNEL_ACCESS_TOKEN,
    'LINE_CHANNEL_SECRET': LINE_CHANNEL_SECRET,
    'OPENAI_API_KEY': OPENAI_API_KEY,
}

missing_vars = [var_name for var_name, var_value in required_vars.items() if not var_value]

if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
