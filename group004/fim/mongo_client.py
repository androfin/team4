"""MongoDB client for FIM events"""
import time
import ssl
import certifi
from typing import Optional, Dict, Any, List
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

from .config import MONGO_URI, MONGO_DB_NAME, MONGO_COLLECTION_NAME, AGENT_ID

_mongo_client: Optional[MongoClient] = None
_mongo_collection = None


def get_mongo_connection():
    """Get MongoDB connection (singleton pattern)"""
    global _mongo_client, _mongo_collection
    
    if not MONGO_URI:
        return None
    
    if _mongo_client is None:
        try:
            _mongo_client = MongoClient(
                MONGO_URI,
                serverSelectionTimeoutMS=10000,
                connectTimeoutMS=10000,
                socketTimeoutMS=10000,
                tlsCAFile=certifi.where()
            )
            _mongo_client.admin.command('ping')
            _mongo_collection = _mongo_client[MONGO_DB_NAME][MONGO_COLLECTION_NAME]
            print(f"[MONGO] Connected to MongoDB database: {MONGO_DB_NAME}")
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            print(f"[MONGO] Failed to connect to MongoDB: {e}")
            _mongo_client = None
            _mongo_collection = None
        except Exception as e:
            print(f"[MONGO] Unexpected error: {e}")
            _mongo_client = None
            _mongo_collection = None
    
    return _mongo_collection


def send_event_to_mongo(event: Dict[str, Any]) -> bool:
    """Insert a single FIM event document into MongoDB
    
    Args:
        event: Event document to insert
    
    Returns:
        True if successful, False otherwise
    """
    collection = get_mongo_connection()
    if collection is None:
        return False
    
    try:
        event["agent_id"] = AGENT_ID
        collection.insert_one(event)
        return True
    except Exception as e:
        print(f"[MONGO] Failed to send event: {e}")
        return False


def get_events_from_mongo(limit: int = 100, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get events from MongoDB
    
    Args:
        limit: Maximum number of events to return
        event_type: Optional filter by event type
    
    Returns:
        List of event documents
    """
    collection = get_mongo_connection()
    if collection is None:
        return []
    
    try:
        query = {}
        if event_type and event_type != "all":
            query["event_type"] = event_type
        
        cursor = collection.find(query).sort("timestamp", -1).limit(limit)
        return list(cursor)
    except Exception as e:
        print(f"[MONGO] Failed to get events: {e}")
        return []


def is_mongo_connected() -> bool:
    """Check if MongoDB is connected
    
    Returns:
        True if connected, False otherwise
    """
    return get_mongo_connection() is not None
