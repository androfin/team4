"""Configuration settings for FIM system"""
import os
import socket

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIM_DIR = os.path.dirname(os.path.abspath(__file__))

WATCH_DIRECTORY = os.path.join(BASE_DIR, "watched")

DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "fim_events.db")

MONGO_URI = os.environ.get("MONGODB_URI", "")
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "fim")
MONGO_COLLECTION_NAME = os.environ.get("MONGO_COLLECTION_NAME", "events")

ENDPOINT_NAME = os.environ.get("ENDPOINT_NAME", "replit_agent")
AGENT_ID = os.environ.get("AGENT_ID", socket.gethostname())

FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5000
