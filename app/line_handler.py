"""
LINE 
oUh!D

d!D†¨U LINE 
oãˆ&ﬁÜ(
"""

import logging
from linebot.models import MessageEvent, TextSendMessage
from linebot import LineBotApi

from app.gpt_processor import process_message, BookkeepingEntry
from app.webhook_sender import send_to_webhook

logger = logging.getLogger(__name__)


def format_confirmation_message(entry: BookkeepingEntry) -> str:
    """
    <3∫ç
o

    o:@	ÕÅM+óåÑ—Mc	

    Args:
        entry: BookkeepingEntry iˆ

    Returns:
        str: <Ñ∫ç
o
    """
    # ó—Mc	
    —Mc = entry.üc—M * entry./á

    message = f""" 3ü

Â{entry.Â}
¡{entry.¡}
—Mc	{—Mc:.0f} C
ÿ>π{entry.ÿ>π}
^{entry.^}
≈Å'{entry.≈Å'}
§ID{entry.§ID}"""

    # Çú	0™†

    if entry.0™:
        message += f"\n0™{entry.0™}"

    return message


def handle_text_message(event: MessageEvent, line_bot_api: LineBotApi) -> None:
    """
    UáW
oÑ;A

    A
    1. ÷ó(
oáW
    2. |Î GPT Uhê
    3. Â∫3 í | webhook + ﬁÜ∫ç
    4. Â∫q í ﬁÜ GPT Ñﬁ…
    5. /§U í ﬁÜÀÑ/§
o

    Args:
        event: LINE MessageEvent
        line_bot_api: LINE Bot API Êã
    """
    user_message = event.message.text
    reply_token = event.reply_token

    logger.info(f"Received message: {user_message}")

    try:
        # |Î GPT U
        entry = process_message(user_message)

        if entry.intent == "bookkeeping":
            # | webhook
            success = send_to_webhook(entry)

            if success:
                # üﬁÜ∫ç
o
                reply_text = format_confirmation_message(entry)
            else:
                # 1W–:(
                reply_text = "3«ôU1WÀåÕf"

        elif entry.intent == "conversation":
            # qﬁÜ GPT ÑáW
            reply_text = entry.response_text

        else:
            reply_text = "±I!’„®Ñ
o"

        # ﬁÜ LINE (
        line_bot_api.reply_message(
            reply_token,
            TextSendMessage(text=reply_text)
        )

        logger.info(f"Replied to user: {reply_text[:50]}...")

    except ValueError as e:
        # «ôWI/§
        logger.error(f"Validation error: {e}")
        line_bot_api.reply_message(
            reply_token,
            TextSendMessage(text="±I
o<	§À∫çåçf")
        )

    except Exception as e:
        # v÷/§
        logger.error(f"Error handling message: {e}")
        line_bot_api.reply_message(
            reply_token,
            TextSendMessage(text="±IÓM!’U®Ñ
oÀåçf")
        )
