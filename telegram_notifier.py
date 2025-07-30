import logging
import os
from telegram import Bot
from telegram.error import TelegramError
from telegram.constants import ParseMode # New import for ParseMode
import asyncio # Needed for async operations

# Renamed and updated to escape all Markdown V2 special characters
def escape_markdown_v2(text):
    """
    Escapes special Markdown V2 characters in the given text for Telegram messages.
    Characters to escape: _, *, [, ], (, ), ~, `, >, #, +, -, =, |, {, }, ., !
    """
    # Order matters for some replacements, e.g., escape backslashes first
    text = text.replace('\\', '\\\\')
    text = text.replace('_', '\\_')
    text = text.replace('*', '\\*')
    text = text.replace('[', '\\[')
    text = text.replace(']', '\\]')
    text = text.replace('(', '\\(')
    text = text.replace(')', '\\)')
    text = text.replace('~', '\\~')
    text = text.replace('`', '\\`')
    text = text.replace('>', '\\>')
    text = text.replace('#', '\\#')
    text = text.replace('+', '\\+')
    text = text.replace('-', '\\-') # This is the culprit for your current error!
    text = text.replace('=', '\\=')
    text = text.replace('|', '\\|')
    text = text.replace('{', '\\{')
    text = text.replace('}', '\\}')
    text = text.replace('.', '\\.')
    text = text.replace('!', '\\!')
    return text

async def send_telegram_message(bot_token, chat_id, message_text):
    """
    Sends a message to the configured Telegram chat ID using the bot.
    """
    if not bot_token or not chat_id:
        logging.error("Telegram BOT_TOKEN or CHAT_ID is not provided. Cannot send message.")
        return

    try:
        bot = Bot(token=bot_token)
        # Ensure ParseMode is set to MARKDOWN_V2
        await bot.send_message(chat_id=chat_id, text=message_text, parse_mode=ParseMode.MARKDOWN_V2)
        logging.info("Telegram text message sent successfully.")
    except TelegramError as e:
        logging.error(f"Failed to send Telegram text message: {e}")
        logging.error(f"Telegram API Error details: {e.message}")
    except Exception as e:
        logging.error(f"An unexpected error occurred while sending Telegram text message: {e}")

async def send_telegram_photo(bot_token, chat_id, photo_path, caption=None):
    """
    Sends a photo to the configured Telegram chat ID with an optional caption.
    """
    if not bot_token or not chat_id:
        logging.error("Telegram BOT_TOKEN or CHAT_ID is not provided. Cannot send photo.")
        return
    
    if not os.path.exists(photo_path):
        logging.error(f"Photo file not found at path: {photo_path}. Cannot send photo.")
        return

    try:
        bot = Bot(token=bot_token)
        with open(photo_path, 'rb') as photo_file:
            await bot.send_photo(chat_id=chat_id, photo=photo_file, caption=caption, parse_mode=ParseMode.MARKDOWN_V2)
        logging.info(f"Telegram photo sent successfully: {photo_path}")
    except TelegramError as e:
        logging.error(f"Failed to send Telegram photo: {e}")
        logging.error(f"Telegram API Error details for photo: {e.message}")
    except Exception as e:
        logging.error(f"An unexpected error occurred while sending Telegram photo: {e}")
