"""Configuration settings for FIM system"""
import os

# Directory to monitor
WATCH_DIRECTORY = os.path.join(os.path.dirname(os.path.dirname(__file__)), "watched")

# Database path
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DB_PATH = os.path.join(DATA_DIR, "fim_events.db")

# Endpoint identifier for this agent
ENDPOINT_NAME = "local_agent"

# Flask settings
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5000





