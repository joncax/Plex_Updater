import logging
from datetime import datetime
import os
import json
from telegram import Update
from telegram.ext import ContextTypes
from telegram import ReplyKeyboardMarkup, KeyboardButton

# Import functions from other modules
import telegram_notifier
import media_scraper

# Setup logging for this module
logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command and displays a custom keyboard."""
    user = update.effective_user
    logger.info(f"User {user.full_name} ({user.id}) sent /start command.")

    # Define the custom keyboard layout
    keyboard = [
        [KeyboardButton("/help"), KeyboardButton("/status")],
        [KeyboardButton("/search"), KeyboardButton("/recent")],
        [KeyboardButton("/update")]
    ]
    # Create the ReplyKeyboardMarkup object
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

    await update.message.reply_html(
        f"Hi {user.mention_html()}! 👋\n"
        "I'm your Plex Updater Bot. I'll keep you informed about new content and removals in your Plex library.\n"
        "You can use the commands below or type them directly.",
        reply_markup=reply_markup # Attach the custom keyboard
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /help command."""
    user = update.effective_user
    logger.info(f"User {user.full_name} ({user.id}) sent /help command.")
    help_text = (
        "Here are the commands you can use:\n\n"
        "*/start* \\- Greet the bot and get an introduction\\.\n"
        "*/help* \\- Show this help message\\.\n"
        "*/status* \\- Get the last scan time and current library totals\\.\n"
        "*/search <query>* \\- Search for movies/series by title \\(e\\.g\\., `/search Matrix`\\)\\.\n"
        "*/recent <number>* \\- List the N most recently added items \\(e\\.g\\., `/recent 5`\\)\\.\n"
        "*/update* \\- Manually trigger a scan for new/removed content\\.\n"
        "\n"
        "I also send automatic updates when new content is added or removed!"
    )
    # The help_text string itself contains escaped characters, so no need to re-escape the whole thing here.
    await update.message.reply_markdown_v2(help_text)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles the /status command.
    Reports the last scan time and current library totals, including a breakdown per monitored folder.
    """
    user = update.effective_user
    logger.info(f"User {user.full_name} ({user.id}) sent /status command.")

    # Access data stored in bot_data by main.py
    config = context.bot_data.get('config')
    script_dir = context.bot_data.get('script_dir')
    media_metadata_cache = context.bot_data.get('media_metadata_cache', {}) # Get the shared cache
    # Get the current_folder_state which contains counts per monitored path
    current_folder_state = context.bot_data.get('current_folder_state', {})
    monitored_folders_config = config.get('monitored_folders', [])

    if not config or not script_dir:
        logger.error("Config or script_dir not found in bot_data for status command.")
        await update.message.reply_text("Error: Bot configuration not loaded. Please inform the administrator.")
        return

    folder_list_file = config['app_settings']['folder_list_file']

    # Read folder_list.json to get last_updated timestamp
    try:
        full_folder_list_path = os.path.join(script_dir, folder_list_file)
        if os.path.exists(full_folder_list_path):
            with open(full_folder_list_path, 'r', encoding='utf-8') as f:
                folder_state_data = json.load(f)
            last_updated = folder_state_data.get("last_updated", "N/A")
            if last_updated != "N/A":
                try:
                    dt_object = datetime.fromisoformat(last_updated)
                    last_updated_formatted = dt_object.strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    last_updated_formatted = last_updated
            else:
                last_updated_formatted = "N/A (No previous scan data)"
        else:
            last_updated_formatted = "N/A (folder_list.json not found)"
    except Exception as e:
        logger.error(f"Error reading folder_list.json for status command: {e}")
        # Only escape the error string, not the whole message
        last_updated_formatted = f"Error: {telegram_notifier.escape_markdown_v2(str(e))}"

    total_items_in_cache = len(media_metadata_cache)

    # Build raw message parts, then escape the final combined string
    raw_status_message_parts = []
    raw_status_message_parts.append(f"*Plex Updater Status* - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    raw_status_message_parts.append(f"*Last Scan:* {last_updated_formatted}\n")
    raw_status_message_parts.append(f"*Total Unique Items in Library:* {total_items_in_cache}\n\n")

    raw_status_message_parts.append("*Library Breakdown:*\n")
    if current_folder_state:
        for folder_path_key in monitored_folders_config:
            base_folder_name = os.path.basename(folder_path_key)
            count = len(current_folder_state.get(folder_path_key, set()))
            raw_status_message_parts.append(f"  *{base_folder_name}*: {count} folders\n")
    else:
        raw_status_message_parts.append("  _No detailed breakdown available yet. Run /update to populate library data._\n")

    # Escape the entire combined message before sending
    final_status_message = telegram_notifier.escape_markdown_v2("".join(raw_status_message_parts))
    await update.message.reply_markdown_v2(final_status_message)


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles the /search command.
    Searches for media by title in the cached metadata.
    """
    user = update.effective_user
    logger.info(f"User {user.full_name} ({user.id}) sent /search command with args: {context.args}")

    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_markdown_v2(
            telegram_notifier.escape_markdown_v2("Please provide a search query. Example: `/search Matrix`")
        )
        return

    media_metadata_cache = context.bot_data.get('media_metadata_cache', {})
    if not media_metadata_cache:
        await update.message.reply_text("The media library data is not yet loaded or is empty. Please run /update first.")
        return

    search_results = []
    for folder_name, metadata in media_metadata_cache.items():
        title = metadata.get('title', folder_name)
        if query.lower() in title.lower():
            search_results.append(metadata)

    if not search_results:
        await update.message.reply_markdown_v2(
            telegram_notifier.escape_markdown_v2(f"No results found for '{query}'.")
        )
        return

    search_results.sort(key=lambda x: int(x.get('year', 0)) if x.get('year', '').isdigit() else 0, reverse=True)

    response_messages = []
    # Build raw message parts, then escape the final combined string
    raw_current_message = f"*Search results for '{query}':*\n\n"
    
    for i, item in enumerate(search_results):
        item_title = item.get('title', 'N/A')
        item_year = item.get('year', 'N/A')
        item_genre = item.get('genre', 'N/A')
        item_plot = item.get('plot', 'No plot available.')
        
        if len(item_plot) > 100:
            item_plot = item_plot[:100].rsplit(' ', 1)[0] + '...'

        # Construct raw item_text
        raw_item_text = (
            f"*{item_title}* ({item_year})\n"
            f"  Genre: {item_genre}\n"
            f"  Plot: {item_plot}\n\n"
        )

        if len(raw_current_message) + len(raw_item_text) > 3500:
            response_messages.append(raw_current_message)
            raw_current_message = f"*Search results for '{query}' (cont.):*\n\n"
        
        raw_current_message += raw_item_text
    
    response_messages.append(raw_current_message)

    for raw_msg in response_messages:
        # Escape each message part before sending
        await update.message.reply_markdown_v2(telegram_notifier.escape_markdown_v2(raw_msg))
        await asyncio.sleep(0.1)


async def recent_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles the /recent command.
    Lists the N most recently added items based on 'added_timestamp'.
    """
    user = update.effective_user
    logger.info(f"User {user.full_name} ({user.id}) sent /recent command with args: {context.args}")

    num_recent = 3 # Default number of recent items
    if context.args:
        try:
            num_recent = int(context.args[0])
            if num_recent <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_markdown_v2(
                telegram_notifier.escape_markdown_v2("Please provide a valid number for recent items. Example: `/recent 3`")
            )
            return
    
    media_metadata_cache = context.bot_data.get('media_metadata_cache', {})
    if not media_metadata_cache:
        await update.message.reply_text("The media library data is not yet loaded or is empty. Please run /update first.")
        return

    # Filter items that have 'added_timestamp' and sort them
    recent_items = []
    for folder_name, metadata in media_metadata_cache.items():
        if 'added_timestamp' in metadata:
            try:
                # Convert ISO format string to datetime object for proper sorting
                metadata['added_datetime'] = datetime.fromisoformat(metadata['added_timestamp'])
                recent_items.append(metadata)
            except ValueError:
                logger.warning(f"Invalid added_timestamp format for '{folder_name}': {metadata['added_timestamp']}")
                continue

    if not recent_items:
        await update.message.reply_markdown_v2(
            telegram_notifier.escape_markdown_v2("No recently added items found with timestamps.")
        )
        return

    recent_items.sort(key=lambda x: x['added_datetime'], reverse=True)

    recent_items_to_display = recent_items[:num_recent]

    response_messages = []
    # Build raw message parts, then escape the final combined string
    raw_current_message = f"*Most Recently Added Items (Top {num_recent}):*\n\n"

    for item in recent_items_to_display:
        item_title = item.get('title', 'N/A')
        item_year = item.get('year', 'N/A')
        item_added_timestamp = item['added_datetime'].strftime("%Y-%m-%d %H:%M")
        
        # Construct raw item_text
        raw_item_text = (
            f"*{item_title}* ({item_year})\n"
            f"  Added: {item_added_timestamp}\n\n"
        )
        
        if len(raw_current_message) + len(raw_item_text) > 3500:
            response_messages.append(raw_current_message)
            raw_current_message = f"*Most Recently Added Items (cont.):*\n\n"
        
        raw_current_message += raw_item_text
    
    response_messages.append(raw_current_message)

    for raw_msg in response_messages:
        # Escape each message part before sending
        await update.message.reply_markdown_v2(telegram_notifier.escape_markdown_v2(raw_msg))
        await asyncio.sleep(0.1)


async def update_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles the /update command.
    Manually triggers a periodic folder scan.
    """
    user = update.effective_user
    logger.info(f"User {user.full_name} ({user.id}) sent /update command.")

    # Get the periodic_folder_scan function from bot_data
    periodic_scan_function = context.bot_data.get('periodic_scan_function')

    if periodic_scan_function:
        await update.message.reply_text("Initiating a manual library scan. I'll notify you when it's complete or if new content is found!")
        # Trigger the scan. Pass the context so it has access to necessary data.
        await periodic_scan_function(context)
        # The periodic_folder_scan function itself will send the final update message.
    else:
        logger.error("periodic_scan_function not found in bot_data.")
        await update.message.reply_text("Error: Unable to trigger manual scan. Please inform the administrator.")
