# Plex Updater Bot

### 🎥 Keep Your Plex Library in Sync with Telegram Notifications!
The Plex Updater Bot is a Python-based Telegram bot designed to automatically monitor your local Plex media folders for changes. It detects new movies/series added and existing ones removed, fetches rich metadata (like plot, genre, year, poster) from OMDb, and sends real-time notifications directly to your Telegram chat. It also provides interactive commands to query your library and runs robustly as a Windows Service.

Say goodbye to manually checking your Plex library for new content!

### ✨ Features
- **Automated Folder Monitoring:** Scans specified local directories for new and removed media folders.
- **Real-time Telegram Notifications:**
    - Sends rich alerts with title, year, genre, plot summary, and poster image for new content.
    - Notifies you when media is removed.
    - Supports configurable "no change" messages.
    - Handles long messages by splitting them into parts.
    - All messages are beautifully formatted using Telegram's Markdown V2.

- **OMDb Metadata Integration:** Automatically fetches comprehensive movie/series metadata (plot, genre, poster URL, IMDb ID) using the OMDb API.
- **Local Poster Management:** Downloads and stores movie/series posters locally, and cleans them up when media is removed.
- **Persistent Data Storage:** Uses folder_list.json to track folder states and media_metadata.json to cache OMDb data, ensuring continuity between runs.

- **Interactive Telegram Commands:**
    - /start: Greets you and provides a custom keyboard menu for easy navigation.
    - /help: Displays a list of all available commands.
    - /status: Shows the bot's last scan time, total unique items, and a detailed breakdown of folders per monitored path.
    - /update: Manually triggers an immediate scan for changes.
    - /search <query>: Search for movies/series by title (supports partial matches, e.g., /search China).
    - /recent <number>: Lists the N most recently added items (e.g., /recent 5).
- **Telegram Heartbeat:** A configurable feature that sends periodic "I'm alive!" messages to confirm the bot is running and connected.
- **Windows Service Deployment:** Configured to run reliably in the background as a Windows Service using NSSM, ensuring automatic startup and crash recovery.

### ⚙️ How It Works
1. **Initialization:** The bot starts, loads configuration from config.json, and sets up logging.
2. **Scanning:** It periodically (or on manual /update) scans your configured media folders.
3. **Comparison:** It compares the current state of your folders with the last saved state (folder_list.json).
4. **Metadata & Posters:** For any new folders, it parses the folder name to extract title and year, queries the OMDb API for metadata, and downloads the corresponding poster. This data is cached in media_metadata.json.
5. **Notifications:** Based on detected changes (additions or removals), it constructs rich Telegram messages (with posters for new content) and sends them to your designated chat.
6. **Persistence:** The updated folder state and media metadata cache are saved back to their respective JSON files for the next run.
7.**Heartbeat:** If enabled, a periodic message is sent to confirm the bot's operational status.
8. **Service Mode:** NSSM ensures the Python script runs continuously in the background, handles restarts, and redirects output to dedicated logs.

### 🚀 Getting Started
Follow these steps to set up and run your Plex Updater Bot.

#### Prerequisites
    - Before you begin, ensure you have the following:
    - **Python 3.8+:** Download from python.org.
    - **Telegram Bot Token:** Create a new bot by chatting with @BotFather on Telegram.
    - **Telegram Group Chat ID:** Add your bot to a Telegram group. Then, send /id to @RawDataBot in that group to get its chat ID (it will be a negative number, e.g., -1234567890).
    - **OMDb API Key:** Get a free API key from OMDb API.
    - **NSSM (Non-Sucking Service Manager):** Download the latest stable release from nssm.cc/download. Extract the .zip file to a convenient location (e.g., C:\NSSM).

1. **Project Setup**
    1. **Create Project Directory:** Create a dedicated folder for your bot, e.g., C:\Scripts\Plex_Updater.
    2. **Download Files:** Place all the bot's Python script files (main.py, config_manager.py, telegram_notifier.py, media_scraper.py, telegram_bot_handler.py) into this directory.
    3. **Install Python Dependencies:** Open a command prompt or PowerShell, navigate to your project directory, and run:

    pip install python-telegram-bot aiohttp

2. **Configuration** (config.json)
Create a file named config.json in your project directory (C:\Scripts\Plex_Updater) with the following content. **Remember to replace the placeholder values with your actual tokens, IDs, and paths.**

{
    "monitored_folders": [
        "Z:\\MOVIES",
        "Z:\\TV_Series"
    ],
    "app_settings": {
        "log_file": "plex_updater.log",
        "folder_list_file": "folder_list.json",
        "max_telegram_message_length": 4000,
        "send_no_change_message": false,
        "heartbeat_enabled": true,
        "heartbeat_interval_hours": 6
    },
    "telegram": {
        "bot_token": "YOUR_BOT_TOKEN_HERE",
        "chat_id": "YOUR_GROUP_CHAT_ID_HERE"
    },
    "omdb_api": {
        "api_key": "YOUR_OMDB_API_KEY_HERE",
        "posters_directory": "posters"
    }
}

    - monitored_folders: List the absolute paths to your Plex media folders. Use double backslashes (\\) for Windows paths.
    - bot_token: Your Telegram bot's API token.
    - chat_id: The ID of your Telegram group chat (must be negative).
    - api_key: Your OMDb API key.
    - heartbeat_enabled: Set to true to enable periodic heartbeat messages.
    - heartbeat_interval_hours: Frequency of heartbeat messages in hours.
    - posters_directory: Name of the subfolder where posters will be saved (e.g., C:\Scripts\Plex_Updater\posters).

3. Create Batch File (start_bot.bat)
Create a file named start_bot.bat in your project directory (C:\Scripts\Plex_Updater) with the following content. **Customize the paths to match your system.**

@echo off
REM Change directory to where your main.py script is located
cd "C:\Scripts\Plex_Updater"

REM Activate your Python virtual environment if you are using one:
REM For example: "C:\path\to\your\venv\Scripts\activate.bat"
REM If you are not using a venv, you can comment out or remove the line below:
REM call "C:\path\to\your\venv\Scripts\activate.bat"

REM Run your main.py script
"C:\Program Files\Python311\python.exe" main.py

- cd "C:\Scripts\Plex_Updater": Crucial: Change this to your actual project directory.
- "C:\Program Files\Python311\python.exe": Crucial: Change this to the full path to your Python executable (python.exe). You can find this by typing where python in your command prompt.
- Virtual Environment (Optional): If you use a virtual environment, uncomment the call line and provide the correct path to its activate.bat file.

4. **Install as Windows Service (NSSM)**
This step allows the bot to run continuously in the background.

    1. **Open Command Prompt as Administrator:** Search for cmd, right-click, and select "Run as administrator."
    2. **Navigate to NSSM:** In the command prompt, cd into the win64 (or win32) folder where you extracted NSSM.

        cd "C:\NSSM\nssm-2.24\win64"

        (Adjust path to your NSSM location)

    3. **Install the Service:** Run the NSSM installer GUI:

        .\nssm install PlexUpdaterBot

    4. **Configure NSSM GUI:**
        - **Application Tab:**
            - Path: Select your start_bot.bat file (e.g., C:\Scripts\Plex_Updater\start_bot.bat).
            - Startup directory: This should auto-populate.
        - **Details Tab:**
            - Display name: Plex Updater Bot
            - Description: Monitors Plex media folders and sends Telegram notifications for changes.
            - Startup type: Automatic

        - **Log On Tab:** Local System account
        - **Exit Actions Tab:**
            - Restart Action: Restart Application
            - Delay: 1000 (1 second)
        - **I/O Tab:**
            - Output (stdout): C:\Scripts\Plex_Updater\bot_output.log
            - Error (stderr): C:\Scripts\Plex_Updater\bot_error.log
        - Leave other tabs as default.
    5. **Click "Install Service"**. You should see a success message.

5. **Start the Service**
    1. **Open Windows Services Manager:** Press Win + R, type services.msc, and press Enter.
    2. **Find your service:** Locate Plex Updater Bot in the list.
    3. **Start the service:** Right-click on Plex Updater Bot and select Start. The status should change to "Running."

🤖 **Bot Usage**
Once the service is running, interact with your bot in your Telegram group:
    - /start: Get a welcome message and a convenient custom keyboard menu.
    - /help: See a list of all commands and their usage.
    - /update: Manually trigger an immediate scan of your monitored folders. The bot will send notifications if new content or removals are detected.
    - /status: Get a summary of the bot's current status, including the last scan time and a breakdown of items per monitored folder.
    - /search <query>: Search for media in your library by title. Example: /search China (will find "Big Trouble in Little China").
    - /recent <number>: List the most recently added items. Example: /recent 3 to see the top 3.

📁 **Project Structure**
Plex_Updater/

├── main.py

├── config_manager.py

├── telegram_notifier.py

├── media_scraper.py

├── telegram_bot_handler.py

├── config.json

├── start_bot.bat

├── plex_updater.log       (Generated by bot)

├── folder_list.json       (Generated by bot)

├── media_metadata.json    (Generated by bot)

├── posters/               (Generated by bot, stores downloaded posters)

├── bot_output.log         (Generated by NSSM)

└── bot_error.log          (Generated by NSSM)

⚠️ **Troubleshooting**
- **Bot not responding / Service not starting:**
    - Check services.msc: Is Plex Updater Bot running? Try restarting it.
    - Examine bot_error.log and bot_output.log for errors from the service wrapper.
    - Check plex_updater.log for Python script-level errors.
    - Verify all paths in config.json and start_bot.bat are correct.
    - Ensure Python dependencies are installed (pip list).

- **Telegram messages not sending:**
    - Verify bot_token and chat_id in config.json are correct.
    - Check plex_updater.log for "Failed to send Telegram message" errors.
    - Ensure your bot has permission to send messages in the group.
    - /recent or /search return "empty data" / "no results":
    - Ensure you have run /update at least once after starting the bot. The bot needs to scan your folders and populate media_metadata.json before these commands can find data.
    - Check if media_metadata.json exists and contains data.

- **Markdown V2 parsing errors (Can't parse entities: character 'X' is reserved...):**
    - This indicates a special Markdown V2 character was not properly escaped (\X). While efforts have been made to escape all dynamic content, review the message construction in telegram_bot_handler.py if new errors appear.

- **OMDb API issues:**
    - Check plex_updater.log for "Failed to fetch metadata from OMDb" errors.
    - Verify your omdb_api_key in config.json is correct and active.
    - Ensure your server has internet access to http://www.omdbapi.com/.

💡 **Future Enhancements**
- **Advanced Error Handling:** Implement more specific error alerts for critical failures.
- **Telegram-based Configuration:** Allow changing some config.json settings directly via bot commands.
- **User Whitelisting:** Restrict bot command access to specific Telegram user IDs.
- **Enriched Output:** Add more metadata fields (e.g., IMDb rating, director, actors) to search and recent results.
- Media Type Filtering: Allow filtering search/recent results by "movie" or "series".
- **"What's New Since My Last Check?":** A command to show only items added since the user's last personal query.
- **Web Dashboard:** Develop a simple local web interface for monitoring and control.
- **Database Integration:** Migrate from JSON files to a lightweight database (e.g., SQLite) for data storage.

This README provides a complete guide for anyone looking to set up, use, or understand your Plex Updater Bot.
