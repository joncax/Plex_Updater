import aiohttp
import logging
import re
import os
import json
from datetime import datetime

# Setup logging for this module
logger = logging.getLogger(__name__)

# --- Configuration (Internal to scraper, but depends on main config) ---
# This file will store the detailed metadata fetched from OMDb
MEDIA_METADATA_FILE = "media_metadata.json"

# --- Helper Functions ---

def parse_folder_name(folder_name):
    """
    Parses a folder name to extract a potential movie/series title and year.
    Assumes common formats like "Movie Title (YYYY)", "Movie.Title.YYYY", "Movie-Title-YYYY".
    Returns a tuple (title, year) or (None, None) if parsing fails.
    """
    # Try to find (YYYY) at the end
    match_paren_year = re.search(r'^(.*?)\s*\((\d{4})\)$', folder_name)
    if match_paren_year:
        title = match_paren_year.group(1).strip()
        year = match_paren_year.group(2)
        return title, year
    
    # Try to find common separators followed by YYYY at the end
    match_sep_year = re.search(r'^(.*?)[._-]?(\d{4})$', folder_name)
    if match_sep_year:
        title = match_sep_year.group(1).replace('.', ' ').replace('-', ' ').strip()
        year = match_sep_year.group(2)
        return title, year

    # If no year found, just return the folder name as title and None for year
    logger.warning(f"Could not reliably parse year from folder name: '{folder_name}'. Proceeding with title only.")
    return folder_name.strip(), None

def get_media_metadata_file_path(script_dir):
    """Returns the full path to the media_metadata.json file."""
    return os.path.join(script_dir, MEDIA_METADATA_FILE)

def read_media_metadata(file_path):
    """
    Reads the cached media metadata from a JSON file.
    Returns a dictionary of metadata (folder_name -> metadata_dict).
    Returns an empty dict if the file doesn't exist or is invalid.
    """
    try:
        if not os.path.exists(file_path):
            logger.info(f"Media metadata file '{file_path}' not found. Starting with empty cache.")
            return {}
        with open(file_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
            logger.info(f"Successfully loaded {len(metadata)} entries from media metadata file.")
            return metadata
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Error reading or parsing media metadata file '{file_path}': {e}. Starting with empty cache.")
        return {}
    except Exception as e:
        logger.error(f"An unexpected error occurred while reading media metadata file '{file_path}': {e}")
        return {}

def write_media_metadata(file_path, metadata_dict):
    """
    Writes the current media metadata dictionary to a JSON file.
    """
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(metadata_dict, f, indent=4, ensure_ascii=False)
        logger.info(f"Successfully wrote {len(metadata_dict)} entries to media metadata file.")
    except Exception as e:
        logger.error(f"Error writing to media metadata file '{file_path}': {e}")

async def fetch_media_metadata_from_omdb(title, year, omdb_api_key):
    """
    Fetches movie or TV series metadata from OMDb API using aiohttp.
    Returns a dictionary with metadata or None if not found/error.
    """
    if not omdb_api_key:
        logger.error("OMDb API key is not configured. Cannot fetch metadata.")
        return None

    base_url = "http://www.omdbapi.com/"
    params = {'t': title, 'apikey': omdb_api_key}
    if year:
        params['y'] = year # Add year to search parameters if available

    try:
        logger.info(f"Fetching metadata for '{title}' (Year: {year if year else 'N/A'}) from OMDb API...")
        async with aiohttp.ClientSession() as session:
            async with session.get(base_url, params=params) as response:
                response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
                data = await response.json()

                if data.get('Response') == 'True':
                    logger.info(f"Successfully fetched metadata for '{title}'.")
                    # Extract relevant fields
                    metadata = {
                        "title": data.get('Title'),
                        "year": data.get('Year'),
                        "rated": data.get('Rated'),
                        "released": data.get('Released'),
                        "runtime": data.get('Runtime'),
                        "genre": data.get('Genre'),
                        "director": data.get('Director'),
                        "actors": data.get('Actors'),
                        "plot": data.get('Plot'),
                        "language": data.get('Language'),
                        "country": data.get('Country'),
                        "poster_url": data.get('Poster'), # External URL
                        "imdb_rating": data.get('imdbRating'),
                        "imdb_id": data.get('imdbID'),
                        "type": data.get('Type'), # movie, series, episode
                        "total_seasons": data.get('totalSeasons'), # for series
                        "last_fetched": datetime.now().isoformat() # Timestamp of fetch
                    }
                    return metadata
                else:
                    logger.warning(f"OMDb API did not find metadata for '{title}' (Year: {year if year else 'N/A'}). Reason: {data.get('Error', 'Unknown error')}")
                    return None
    except aiohttp.ClientError as e:
        logger.error(f"Network or API request error for '{title}': {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching metadata for '{title}': {e}")
        return None

async def download_poster(poster_url, posters_dir, folder_name):
    """
    Downloads a poster image from a URL and saves it to the local posters directory using aiohttp.
    Returns the local path to the saved poster, or None on failure.
    """
    if not poster_url or poster_url == "N/A":
        logger.warning(f"No valid poster URL provided for '{folder_name}'.")
        return None

    # Create posters directory if it doesn't exist
    if not os.path.exists(posters_dir):
        os.makedirs(posters_dir)
        logger.info(f"Created posters directory: '{posters_dir}'.")

    # Sanitize folder_name for filename (replace invalid chars with underscore)
    sanitized_folder_name = re.sub(r'[\\/:*?"<>|]', '_', folder_name)
    # Use a simple filename based on sanitized folder name and poster extension
    # Get extension from URL (e.g., .jpg, .png)
    file_extension = os.path.splitext(poster_url)[1]
    if not file_extension: # Fallback if no extension in URL
        file_extension = ".jpg" 
    
    local_poster_filename = f"{sanitized_folder_name}{file_extension}"
    local_poster_path = os.path.join(posters_dir, local_poster_filename)

    try:
        logger.info(f"Downloading poster for '{folder_name}' from '{poster_url}' to '{local_poster_path}'...")
        async with aiohttp.ClientSession() as session:
            async with session.get(poster_url) as response:
                response.raise_for_status() # Raise an HTTPError for bad responses

                with open(local_poster_path, 'wb') as f:
                    # Read content in chunks asynchronously
                    while True:
                        chunk = await response.content.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
        logger.info(f"Successfully downloaded poster to '{local_poster_path}'.")
        return local_poster_path
    except aiohttp.ClientError as e:
        logger.error(f"Network or download error for poster '{poster_url}': {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred while downloading poster for '{folder_name}': {e}")
        return None

def delete_poster(posters_dir, folder_name):
    """
    Deletes the poster associated with a removed folder.
    """
    # Sanitize folder_name to match the saved filename
    sanitized_folder_name = re.sub(r'[\\/:*?"<>|]', '_', folder_name)
    
    # We need to find the actual file, as extension might vary (.jpg, .png)
    # Iterate through files in posters_dir and find matches
    deleted_count = 0
    if os.path.exists(posters_dir):
        for filename in os.listdir(posters_dir):
            # Check if filename starts with the sanitized folder name (ignoring extension)
            if filename.startswith(sanitized_folder_name):
                full_path = os.path.join(posters_dir, filename)
                try:
                    os.remove(full_path)
                    logger.info(f"Deleted poster file: '{full_path}'.")
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"Error deleting poster '{full_path}': {e}")
    if deleted_count == 0:
        logger.info(f"No poster found to delete for '{folder_name}' in '{posters_dir}'.")