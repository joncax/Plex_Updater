import os
import logging
import json
import asyncio
import telegram_bot_handler
from datetime import datetime

# Import necessary classes from python-telegram-bot
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, JobQueue
from telegram.error import TelegramError # Import TelegramError for specific exception handling

# Import functions from our new modules
import config_manager
import telegram_notifier
import media_scraper

# --- Logging Setup ---
# Initial basic logging config. This will be reconfigured once config.json is loaded.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# --- Global Variables (to be populated from config) ---
# These will be loaded once the bot starts
CONFIG = None
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MEDIA_METADATA_CACHE = {} # Cache for media metadata, shared across bot and scheduled job

# --- Core Functions (from previous versions, now used by scheduled job) ---
# These functions are kept here as they are directly called by periodic_folder_scan
# and need access to global variables (CONFIG, SCRIPT_DIR, MEDIA_METADATA_CACHE).

def get_subfolders(directory_path):
    """
    Scans a given directory path and returns a list of names of its direct subfolders.
    Logs whether the directory exists and its contents.
    """
    subfolders = []
    if not os.path.exists(directory_path):
        logging.warning(f"Monitored folder not found: {directory_path}")
        return subfolders # Return empty list if directory doesn't exist

    logging.info(f"Scanning monitored folder: {directory_path}")
    try:
        for entry_name in os.listdir(directory_path):
            full_path = os.path.join(directory_path, entry_name)
            if os.path.isdir(full_path):
                subfolders.append(entry_name)
        logging.info(f"Found {len(subfolders)} direct subfolders in '{directory_path}'.")
        return subfolders
    except Exception as e:
        logging.error(f"Error accessing directory '{directory_path}': {e}")
        return subfolders

def read_folder_state(file_path):
    """
    Reads the previously recorded folder state from a JSON file.
    Returns a dictionary where keys are monitored paths and values are sets of subfolder names.
    If the file doesn't exist or is invalid, returns an empty dictionary.
    """
    try:
        if not os.path.exists(file_path):
            logging.info(f"'{file_path}' not found. Assuming first run or file deleted.")
            return {}
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            loaded_state = {}
            for path, folders in data.items():
                if path == "last_updated":
                    loaded_state[path] = folders
                else:
                    loaded_state[path] = set(folders)
            logging.info(f"Successfully loaded previous folder state from '{file_path}'.")
            return loaded_state
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Error reading or parsing '{file_path}': {e}. Starting with empty state.")
        return {}
    except Exception as e:
        logging.error(f"An unexpected error occurred while reading '{file_path}': {e}")
        return {}

def write_folder_state(file_path, folder_state_dict):
    """
    Writes the current folder state (dictionary of paths to subfolder names) to a JSON file.
    Ensures subfolder lists are sorted for consistent file output.
    """
    try:
        folder_state_dict["last_updated"] = datetime.now().isoformat()
        serializable_data = {}
        for path, folders in folder_state_dict.items():
            if isinstance(folders, set):
                serializable_data[path] = sorted(list(folders))
            else:
                serializable_data[path] = folders
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(serializable_data, f, indent=4, ensure_ascii=False)
        logging.info(f"Successfully wrote current folder state to '{file_path}'.")
    except Exception as e:
        logging.error(f"Error writing to '{file_path}': {e}")

# --- Scheduled Folder Scan Function ---
async def periodic_folder_scan(context: ContextTypes.DEFAULT_TYPE):
    """
    This function will be run by the JobQueue periodically.
    It encapsulates the original folder scanning, comparison, and notification logic.
    """
    global CONFIG, MEDIA_METADATA_CACHE # Access global config and cache

    if CONFIG is None:
        logging.error("Configuration not loaded for periodic_folder_scan. Skipping scan.")
        return

    logging.info("--- Scheduled Plex Updater Scan Started ---")

    # Get settings from config
    monitored_folders = CONFIG['monitored_folders']
    folder_list_file = CONFIG['app_settings']['folder_list_file']
    bot_token = CONFIG['telegram']['bot_token']
    chat_id = CONFIG['telegram']['chat_id']
    max_telegram_message_length = CONFIG['app_settings']['max_telegram_message_length']
    send_no_change_message = CONFIG['app_settings'].get('send_no_change_message', False)
    
    omdb_api_key = CONFIG['omdb_api']['api_key']
    posters_directory = CONFIG['omdb_api']['posters_directory']
     
    # Ensure posters directory exists
    full_posters_path = os.path.join(SCRIPT_DIR, posters_directory)
    if not os.path.exists(full_posters_path):
        os.makedirs(full_posters_path, exist_ok=True)
        logging.info(f"Created posters directory: {full_posters_path}")
    
    # Get the path to the media_metadata.json file
    media_metadata_file = media_scraper.get_media_metadata_file_path(SCRIPT_DIR)
    # Load existing media metadata cache
    MEDIA_METADATA_CACHE = media_scraper.read_media_metadata(media_metadata_file) # Reload cache
    # CRITICAL FIX: Update the bot_data cache with the reloaded global cache
    context.bot_data['media_metadata_cache'] = MEDIA_METADATA_CACHE

    # 1. Get the list of folders from the previous run (categorized by path)
    old_folder_state = read_folder_state(os.path.join(SCRIPT_DIR, folder_list_file)) # Use full path

    # 2. Get the current list of folders from monitored directories (categorized by path)
    current_folder_state = {}
    total_unique_subfolders = set() # To count overall unique folders
    for folder_path in monitored_folders:
        current_subfolders_in_path = get_subfolders(folder_path)
        current_folder_state[folder_path] = set(current_subfolders_in_path)
        total_unique_subfolders.update(current_subfolders_in_path)

    logging.info(f"Total unique direct subfolders found across all monitored paths: {len(total_unique_subfolders)}")

    # NEW: Store current_folder_state in bot_data for /status command
    context.bot_data['current_folder_state'] = current_folder_state

    # Prepare for categorized logging messages and Telegram message
    telegram_message_parts = []
    has_changes = False
    overall_added_count = 0
    overall_removed_count = 0

    # List to store messages that will be sent as photos (for new content)
    photo_messages_to_send = []
    
    # 3. Compare current and old lists for each monitored folder
    for folder_path in monitored_folders:
        # Get old and current subfolders for the specific path
        old_subfolders_for_path = old_folder_state.get(folder_path, set())
        current_subfolders_for_path = current_folder_state.get(folder_path, set())

        added_for_path = current_subfolders_for_path - old_subfolders_for_path
        removed_for_path = old_subfolders_for_path - current_subfolders_for_path

        overall_added_count += len(added_for_path)
        overall_removed_count += len(removed_for_path)

        # Handle added folders: fetch metadata, download poster, prepare rich message
        if added_for_path:
            has_changes = True
            logging.info(f"\n--- In Folder: {folder_path} ---")
            logging.info("  New folders added:")
            # Escape folder path name for Markdown V2
            telegram_message_parts.append(f"*{telegram_notifier.escape_markdown_v2(os.path.basename(folder_path))}*:")
            telegram_message_parts.append("  *New content added:*")

            for folder_name in sorted(list(added_for_path)):
                logging.info(f"    - {folder_name}")
                
                # Try to fetch metadata and download poster
                title, year = media_scraper.parse_folder_name(folder_name)
                
                # Check if metadata is already in cache and is recent enough (optional: add time check)
                metadata = MEDIA_METADATA_CACHE.get(folder_name)
                if metadata and "last_fetched" in metadata:
                    logging.info(f"Metadata for '{folder_name}' found in cache.")
                else:
                    # Fetch from OMDb if not in cache or too old
                    metadata = await media_scraper.fetch_media_metadata_from_omdb(title, year, omdb_api_key)
                    if metadata:
                        # Add added_timestamp when metadata is first fetched for a new item
                        metadata["added_timestamp"] = datetime.now().isoformat()
                        MEDIA_METADATA_CACHE[folder_name] = metadata # Add to cache

                local_poster_path = None
                if metadata and metadata.get('poster_url') and metadata.get('poster_url') != "N/A":
                    # Download poster if a URL is available
                    local_poster_path = await media_scraper.download_poster(
                        metadata['poster_url'], full_posters_path, folder_name
                    )
                    if local_poster_path:
                        metadata['local_poster_path'] = local_poster_path # Store local path in metadata cache
                        MEDIA_METADATA_CACHE[folder_name] = metadata # Update cache with local path

                # Prepare Telegram message for new content
                if local_poster_path and os.path.exists(local_poster_path):
                    # Build raw caption parts, then escape the final joined string
                    raw_caption_parts = []
                    raw_caption_parts.append(f"*{metadata.get('title', folder_name)}* ({metadata.get('year', 'N/A')})")
                    if metadata.get('genre'):
                        raw_caption_parts.append(f"Genre: {metadata['genre']}")
                    if metadata.get('plot'):
                        plot = metadata['plot']
                        if len(plot) > 200: # Keep plot concise for caption
                            plot = plot[:200].rsplit(' ', 1)[0] + '...'
                        raw_caption_parts.append(f"Plot: {plot}")
                    if metadata.get('imdb_id'):
                        raw_caption_parts.append(f"[IMDb Link](https://www.imdb.com/title/{metadata['imdb_id']}/)")
                    
                    # Escape the entire caption string for Markdown V2
                    final_caption = telegram_notifier.escape_markdown_v2("\n".join(raw_caption_parts))

                    photo_messages_to_send.append({
                        "photo_path": local_poster_path,
                        "caption": final_caption
                    })
                else:
                    # Simple text message if no poster or metadata
                    telegram_message_parts.append(f"    - {telegram_notifier.escape_markdown_v2(folder_name)} (No detailed info/poster)")
            telegram_message_parts.append("\n") # Add a newline for separation in Telegram

        # Handle removed folders: delete poster and metadata
        if removed_for_path:
            has_changes = True
            logging.info(f"\n--- In Folder: {folder_path} ---")
            logging.info("  Folders removed:")
            # Escape folder path name for Markdown V2
            telegram_message_parts.append(f"*{telegram_notifier.escape_markdown_v2(os.path.basename(folder_path))}*:")
            telegram_message_parts.append("  *Content removed:*")
            for folder_name in sorted(list(removed_for_path)):
                logging.info(f"    - {folder_name}")
                telegram_message_parts.append(f"    - {telegram_notifier.escape_markdown_v2(folder_name)}")
                
                # Delete associated poster and metadata from cache
                media_scraper.delete_poster(full_posters_path, folder_name)
                if folder_name in MEDIA_METADATA_CACHE:
                    del MEDIA_METADATA_CACHE[folder_name]
                    logging.info(f"Removed metadata for '{folder_name}' from cache.")
            telegram_message_parts.append("\n") # Add a newline for separation in Telegram
        
        if not added_for_path and not removed_for_path:
            logging.info(f"\n--- In Folder: {folder_path} ---")
            logging.info("  No changes detected.")
    
    
    # Construct the main message header (raw, then escape at the end)
    current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if has_changes:
        raw_main_header = f"*Plex Library Updates!* {current_time_str}\n\n"
        if overall_added_count > 0 and overall_removed_count > 0:
            raw_main_header += f"Found {overall_added_count} new items and {overall_removed_count} removed items.\n\n"
        elif overall_added_count > 0:
                raw_main_header += f"Found {overall_added_count} new items.\n\n"
        elif overall_removed_count > 0:
            raw_main_header += f"Found {overall_removed_count} removed items.\n\n"
    else:
        raw_main_header = f"*Plex Updater Status* {current_time_str}\nNo new content or removals detected.\n\n"

    # Add current library totals to the message (raw, then escape at the end)
    raw_library_totals_parts = ["*Current Library Totals*:"]
    for folder_path in monitored_folders:
        count = len(get_subfolders(folder_path))
        raw_library_totals_parts.append(f"  *{os.path.basename(folder_path)}*: {count} folders")
    raw_library_totals_message = "\n".join(raw_library_totals_parts)

    # Combine header and details for text messages (excluding photo messages)
    # Escape the entire combined string before sending
    full_text_message_content = telegram_notifier.escape_markdown_v2(
        raw_main_header + "\n".join(telegram_message_parts).strip() + "\n\n" + raw_library_totals_message
    )

    # Send photo messages first
    for photo_msg in photo_messages_to_send:
        photo_sent_successfully = False # Flag to track if the photo was truly sent
        try:
            await telegram_notifier.send_telegram_photo(
                bot_token, chat_id, photo_msg["photo_path"], photo_msg["caption"]
            )
            photo_sent_successfully = True # Set flag to True on success
            await asyncio.sleep(0.5) # Small delay between messages
        except TelegramError as e: # Catch specific Telegram API errors
            logging.error(f"Telegram API error sending photo message for {photo_msg.get('caption', 'N/A')}: {e.message}")
        except Exception as e: # Catch any other unexpected errors
            logging.error(f"Unexpected error sending photo message for {photo_msg.get('caption', 'N/A')}: {e}")

        # Only send fallback if photo was NOT successfully sent
        if not photo_sent_successfully:
            logging.info(f"Attempting to send text fallback for: {photo_msg.get('caption', 'N/A')}")
            # The fallback message also needs to be fully escaped
            fallback_text = f"New: {photo_msg.get('caption', 'N/A')}. Check logs for details."
            await telegram_notifier.send_telegram_message(
                bot_token, chat_id, telegram_notifier.escape_markdown_v2(fallback_text)
            )
            await asyncio.sleep(0.5)
    
    
    # Handle remaining text message pagination (if any text messages are left)
    if telegram_message_parts or not has_changes: # If there are text updates or no changes
        # The `full_text_message_content` is already fully escaped above
        if len(full_text_message_content) > max_telegram_message_length:
            logging.info("Text message exceeds max length, attempting to split.")
            
            # Reconstruct the raw parts for splitting
            raw_messages_to_send_text_only = []
            raw_current_part_message = f"*Plex Library Updates (Text message split due to length)*\n\n" # No need to escape this literal
            raw_part_counter = 1
            
            raw_remaining_text_sections = []
            for folder_path in monitored_folders:
                old_subfolders_for_path = old_folder_state.get(folder_path, set())
                current_subfolders_for_path = current_folder_state.get(folder_path, set())

                added_for_path_text_only = [f for f in current_subfolders_for_path - old_subfolders_for_path if f not in [p['caption'].split('(')[0].strip() for p in photo_messages_to_send]]
                
                if added_for_path_text_only:
                    section_content = f"*{os.path.basename(folder_path)}*:\n  *New content added (text-only):*\n" + \
                                      "\n".join([f"    - {f} (No detailed info/poster)" for f in sorted(list(added_for_path_text_only))])
                    raw_remaining_text_sections.append(section_content)

                if removed_for_path:
                    section_content = f"*{os.path.basename(folder_path)}*:\n  *Content removed:*\n" + \
                                      "\n".join([f"    - {f}" for f in sorted(list(removed_for_path))])
                    raw_remaining_text_sections.append(section_content)
            
            for section in raw_remaining_text_sections:
                if len(raw_current_part_message) + len(section) > max_telegram_message_length:
                    raw_messages_to_send_text_only.append(raw_current_part_message.strip())
                    raw_part_counter += 1
                    raw_current_part_message = f"*Plex Library Updates (Part {raw_part_counter})*\n\n"
                raw_current_part_message += section + "\n\n"
            
            if raw_current_part_message.strip() != "":
                raw_messages_to_send_text_only.append(raw_current_part_message.strip())

            for i, raw_msg_part in enumerate(raw_messages_to_send_text_only):
                final_msg_to_send = telegram_notifier.escape_markdown_v2(f"({i+1}/{len(raw_messages_to_send_text_only)}) " + raw_msg_part)
                await telegram_notifier.send_telegram_message(bot_token, chat_id, final_msg_to_send)
                await asyncio.sleep(0.5)

        elif has_changes or send_no_change_message:
            # Send single text message if not too long and changes exist, or if configured to send no-change messages
            # full_text_message_content is already escaped
            if telegram_message_parts or not has_changes:
                await telegram_notifier.send_telegram_message(bot_token, chat_id, full_text_message_content)
        else:
            logging.info("No changes detected and 'send_no_change_message' is false. No Telegram message sent.")


    # 4. Update the folder_list.json with the current state for the next run
    write_folder_state(os.path.join(SCRIPT_DIR, folder_list_file), current_folder_state) # Use full path

    # 5. Update the media_metadata.json cache
    media_scraper.write_media_metadata(media_metadata_file, MEDIA_METADATA_CACHE)

    
    logging.info("--- Scheduled Plex Updater Scan Finished ---")

# --- Heartbeat Function ---
async def send_heartbeat_message(context: ContextTypes.DEFAULT_TYPE):
    """
    Sends a periodic heartbeat message to the Telegram chat.
    """
    global CONFIG
    if CONFIG is None:
        logging.error("Configuration not loaded for heartbeat. Skipping heartbeat.")
        return

    bot_token = CONFIG['telegram']['bot_token']
    chat_id = CONFIG['telegram']['chat_id']
    
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    heartbeat_message = telegram_notifier.escape_markdown_v2(
        f"🧡 *Plex Updater Bot Heartbeat* 🧡\n"
        f"Last check: {current_time}\n"
        f"I'm still running and monitoring your library\\!"
    )
    
    logging.info("Sending heartbeat message.")
    await telegram_notifier.send_telegram_message(bot_token, chat_id, heartbeat_message)


# --- Main Bot Application Setup ---
def main_bot_app():
    """
    Sets up and runs the Telegram Bot application.
    """
    global CONFIG # Access global config

    # Load configuration at startup
    CONFIG = config_manager.load_config()
    if CONFIG is None:
        logging.critical("Failed to load configuration. Exiting bot application.")
        return

    # Reconfigure logging to include file handler based on config
    log_file = CONFIG['app_settings']['log_file']
    for handler in logging.root.handlers[:]: # Remove existing handlers
        logging.root.removeHandler(handler)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    logging.info(f"Logging reconfigured to use file: {log_file}")
    logging.info("--- Starting Plex Updater Telegram Bot ---")

    # Create the Application and pass your bot's token.
    application = Application.builder().token(CONFIG['telegram']['bot_token']).build()

    # Store config and script_dir in bot_data for access in handlers
    application.bot_data['config'] = CONFIG
    application.bot_data['script_dir'] = SCRIPT_DIR
    application.bot_data['media_metadata_cache'] = MEDIA_METADATA_CACHE # Share cache
    # NEW: Store the periodic_folder_scan function in bot_data for /update command
    application.bot_data['periodic_scan_function'] = periodic_folder_scan

    # Get the job queue
    job_queue = application.job_queue

    # Add handlers for commands
    application.add_handler(CommandHandler("start", telegram_bot_handler.start_command))
    application.add_handler(CommandHandler("help", telegram_bot_handler.help_command))
    application.add_handler(CommandHandler("status", telegram_bot_handler.status_command))
    application.add_handler(CommandHandler("search", telegram_bot_handler.search_command))
    application.add_handler(CommandHandler("recent", telegram_bot_handler.recent_command))
    # NEW: Register the update command
    application.add_handler(CommandHandler("update", telegram_bot_handler.update_command))


    # Schedule the periodic folder scan
    # Run every 12 hours (43200 seconds)
    # The first run will happen 0 seconds after the bot starts.
    job_interval_seconds = 12 * 60 * 60 # 12 hours
    job_queue.run_repeating(periodic_folder_scan, interval=job_interval_seconds, first=0)
    logging.info(f"Scheduled periodic folder scan to run every {job_interval_seconds / 3600} hours.")

    # Schedule the heartbeat message if enabled
    if CONFIG['app_settings'].get('heartbeat_enabled', False):
        heartbeat_interval = CONFIG['app_settings'].get('heartbeat_interval_hours', 6) * 60 * 60
        job_queue.run_repeating(send_heartbeat_message, interval=heartbeat_interval, first=heartbeat_interval) # First heartbeat after interval
        logging.info(f"Scheduled heartbeat message to run every {heartbeat_interval / 3600} hours.")
            
    # Run the bot until the user presses Ctrl-C
    logging.info("Bot started. Press Ctrl-C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main_bot_app()
