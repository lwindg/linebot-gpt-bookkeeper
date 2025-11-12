"""
∞ÉäxMn!D

d!D†¨	eåWI@	≈ÅÑ∞Éäx
( python-dotenv û .env îH	eMn
"""

import os
from dotenv import load_dotenv

# 	e .env îH
load_dotenv()

# ≈Å∞Éäx
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')

# x(∞Éäx	-<	
GPT_MODEL = os.getenv('GPT_MODEL', 'gpt-4o-mini')
WEBHOOK_TIMEOUT = int(os.getenv('WEBHOOK_TIMEOUT', '10'))

# WI≈Åäx
required_vars = {
    'LINE_CHANNEL_ACCESS_TOKEN': LINE_CHANNEL_ACCESS_TOKEN,
    'LINE_CHANNEL_SECRET': LINE_CHANNEL_SECRET,
    'OPENAI_API_KEY': OPENAI_API_KEY,
    'WEBHOOK_URL': WEBHOOK_URL,
}

missing_vars = [var_name for var_name, var_value in required_vars.items() if not var_value]

if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
