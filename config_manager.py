import json
import os
import logging

# Get the directory where this script (config_manager.py) is located
# This assumes config.json will be in the same directory as the main script
script_dir = os.path.dirname(os.path.abspath(__file__))
config_file_name = "config.json"
config_file_path = os.path.join(script_dir, config_file_name)

def load_config():
    """
    Loads configuration settings from the config.json file.
    Returns a dictionary containing the configuration.
    Logs an error and exits if the config file cannot be loaded.
    """
    try:
        if not os.path.exists(config_file_path):
            logging.critical(f"Configuration File '{config_file_path}' not found. Please create it.")
            # In a real application, you might raise an exception or provide a default config.
            # For this script, we'll exit as it's a critical dependency.
            return None # Indicate failure to load config
            
        with open(config_file_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            logging.info(f"Configuration loaded from '{config_file_name}'.")
            return config
    except json.JSONDecodeError as e:
        logging.critical(f"Error parsing '{config_file_name}': Invalid JSON format. Details: {e}")
        return None
    except Exception as e:
        logging.critical(f"An unexpeded error occurred while loading '{config_file_name}': {e}")
        return None
