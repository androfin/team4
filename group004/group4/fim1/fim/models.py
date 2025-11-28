"""Database models and data access layer"""
import sqlite3
import os
from typing import Optional, List, Dict, Any
from .config import DB_PATH, DATA_DIR


def init_db() -> None:
    """Create the database and events table if they don't exist"""
    # Ensure data directory exists
    os.makedirs(DATA_DIR, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            file_path TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            hostname TEXT NOT NULL,
            username TEXT NOT NULL,
            hash_before TEXT,
            hash_after TEXT
        )
    """)
    
    # Create index on event_type for faster filtering
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_event_type 
        ON events(event_type)
    """)
    
    # Create index on timestamp for faster ordering
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_timestamp 
        ON events(timestamp)
    """)
    
    # Create file_classification table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS file_classification (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL UNIQUE,
            classification TEXT NOT NULL,
            last_updated_timestamp TEXT NOT NULL,
            endpoint TEXT,
            hostname TEXT,
            username TEXT
        )
    """)
    
    # Create index on file_path for faster lookups
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_file_path 
        ON file_classification(file_path)
    """)
    
    conn.commit()
    conn.close()


def insert_event(data: Dict[str, Any]) -> int:
    """Insert a single event into the database
    
    Args:
        data: Dictionary with keys: event_type, file_path, timestamp,
              endpoint, hostname, username, hash_before, hash_after
    
    Returns:
        The ID of the inserted event
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO events (
            event_type, file_path, timestamp, endpoint,
            hostname, username, hash_before, hash_after
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("event_type"),
        data.get("file_path"),
        data.get("timestamp"),
        data.get("endpoint"),
        data.get("hostname"),
        data.get("username"),
        data.get("hash_before"),
        data.get("hash_after"),
    ))
    
    event_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return event_id


def get_latest_hash(file_path: str) -> Optional[str]:
    """Get the most recent hash_after for a given file path
    
    Args:
        file_path: Path to the file
    
    Returns:
        The most recent hash_after value, or None if not found
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT hash_after FROM events
        WHERE file_path = ? AND hash_after IS NOT NULL
        ORDER BY timestamp DESC
        LIMIT 1
    """, (file_path,))
    
    result = cursor.fetchone()
    conn.close()
    
    return result[0] if result else None


def get_latest_events(limit: int = 100, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get the latest events from the database
    
    Args:
        limit: Maximum number of events to return
        event_type: Optional filter by event type (created/modified/deleted)
    
    Returns:
        List of event dictionaries ordered by timestamp (newest first)
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    if event_type and event_type != "all":
        cursor.execute("""
            SELECT * FROM events
            WHERE event_type = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (event_type, limit))
    else:
        cursor.execute("""
            SELECT * FROM events
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
    
    rows = cursor.fetchall()
    conn.close()
    
    # Convert Row objects to dictionaries
    events = []
    for row in rows:
        events.append({
            "id": row["id"],
            "event_type": row["event_type"],
            "file_path": row["file_path"],
            "timestamp": row["timestamp"],
            "endpoint": row["endpoint"],
            "hostname": row["hostname"],
            "username": row["username"],
            "hash_before": row["hash_before"],
            "hash_after": row["hash_after"],
        })
    
    return events


def get_latest_events_filtered(
    limit: int = 100,
    event_types: Optional[List[str]] = None,
    search_query: Optional[str] = None,
    search_columns: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """Get the latest events with advanced filtering
    
    Args:
        limit: Maximum number of events to return
        event_types: Optional list of event types to filter (created/modified/deleted)
        search_query: Optional search query string
        search_columns: Optional list of columns to search in (if None, searches all)
    
    Returns:
        List of event dictionaries ordered by timestamp (newest first)
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = "SELECT * FROM events WHERE 1=1"
    params = []
    
    # Filter by event types
    if event_types and len(event_types) > 0:
        placeholders = ",".join("?" * len(event_types))
        query += f" AND event_type IN ({placeholders})"
        params.extend(event_types)
    
    # Search query
    if search_query and search_query.strip():
        search_term = f"%{search_query.strip()}%"
        if search_columns and len(search_columns) > 0:
            # Search in specific columns
            column_conditions = []
            for col in search_columns:
                if col in ["timestamp", "event_type", "file_path", "endpoint", "hostname", "username"]:
                    column_conditions.append(f"{col} LIKE ?")
                    params.append(search_term)
            if column_conditions:
                query += " AND (" + " OR ".join(column_conditions) + ")"
        else:
            # Search in all columns
            query += """ AND (
                timestamp LIKE ? OR
                event_type LIKE ? OR
                file_path LIKE ? OR
                endpoint LIKE ? OR
                hostname LIKE ? OR
                username LIKE ?
            )"""
            params.extend([search_term] * 6)
    
    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    # Convert Row objects to dictionaries
    events = []
    for row in rows:
        events.append({
            "id": row["id"],
            "event_type": row["event_type"],
            "file_path": row["file_path"],
            "timestamp": row["timestamp"],
            "endpoint": row["endpoint"],
            "hostname": row["hostname"],
            "username": row["username"],
            "hash_before": row["hash_before"],
            "hash_after": row["hash_after"],
        })
    
    return events


def get_distinct_file_paths(endpoints: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Get distinct file paths with their latest event information
    
    Args:
        endpoints: Optional list of endpoints to filter by
    
    Returns:
        List of dictionaries with file_path and latest event info
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = """
        SELECT DISTINCT
            e1.file_path,
            e1.timestamp as last_timestamp,
            e1.endpoint,
            e1.hostname,
            e1.username
        FROM events e1
        INNER JOIN (
            SELECT file_path, MAX(timestamp) as max_timestamp
            FROM events
            GROUP BY file_path
        ) e2 ON e1.file_path = e2.file_path AND e1.timestamp = e2.max_timestamp
    """
    
    params = []
    if endpoints and len(endpoints) > 0:
        placeholders = ",".join("?" * len(endpoints))
        query += f" WHERE e1.endpoint IN ({placeholders})"
        params.extend(endpoints)
    
    query += " ORDER BY e1.timestamp DESC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    files = []
    for row in rows:
        files.append({
            "file_path": row["file_path"],
            "last_timestamp": row["last_timestamp"],
            "endpoint": row["endpoint"],
            "hostname": row["hostname"],
            "username": row["username"],
        })
    
    return files


def get_file_classification(file_path: str) -> Optional[Dict[str, Any]]:
    """Get classification for a specific file path
    
    Args:
        file_path: Path to the file
    
    Returns:
        Classification dictionary or None if not found
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM file_classification
        WHERE file_path = ?
    """, (file_path,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "id": row["id"],
            "file_path": row["file_path"],
            "classification": row["classification"],
            "last_updated_timestamp": row["last_updated_timestamp"],
            "endpoint": row["endpoint"],
            "hostname": row["hostname"],
            "username": row["username"],
        }
    return None


def upsert_file_classification(
    file_path: str,
    classification: str,
    endpoint: Optional[str] = None,
    hostname: Optional[str] = None,
    username: Optional[str] = None
) -> int:
    """Insert or update file classification
    
    Args:
        file_path: Path to the file
        classification: Classification level (Top Secret, Secret, Confidential, Unclassified)
        endpoint: Optional endpoint
        hostname: Optional hostname
        username: Optional username
    
    Returns:
        The ID of the inserted/updated record
    """
    from datetime import datetime
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Check if record exists
    cursor.execute("SELECT id FROM file_classification WHERE file_path = ?", (file_path,))
    existing = cursor.fetchone()
    
    if existing:
        # Update existing record
        cursor.execute("""
            UPDATE file_classification SET
                classification = ?,
                last_updated_timestamp = ?,
                endpoint = ?,
                hostname = ?,
                username = ?
            WHERE file_path = ?
        """, (classification, timestamp, endpoint, hostname, username, file_path))
        record_id = existing[0]
    else:
        # Insert new record
        cursor.execute("""
            INSERT INTO file_classification (
                file_path, classification, last_updated_timestamp,
                endpoint, hostname, username
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (file_path, classification, timestamp, endpoint, hostname, username))
        record_id = cursor.lastrowid
    
    record_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return record_id


def get_all_classifications(endpoints: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Get all file classifications, optionally filtered by endpoints
    
    Args:
        endpoints: Optional list of endpoints to filter by
    
    Returns:
        List of classification dictionaries
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = "SELECT * FROM file_classification WHERE 1=1"
    params = []
    
    if endpoints and len(endpoints) > 0:
        placeholders = ",".join("?" * len(endpoints))
        query += f" AND endpoint IN ({placeholders})"
        params.extend(endpoints)
    
    query += " ORDER BY last_updated_timestamp DESC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    classifications = []
    for row in rows:
        classifications.append({
            "id": row["id"],
            "file_path": row["file_path"],
            "classification": row["classification"],
            "last_updated_timestamp": row["last_updated_timestamp"],
            "endpoint": row["endpoint"],
            "hostname": row["hostname"],
            "username": row["username"],
        })
    
    return classifications


def get_distinct_endpoints() -> List[str]:
    """Get list of distinct endpoints from events table
    
    Returns:
        List of endpoint strings
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT DISTINCT endpoint FROM events ORDER BY endpoint")
    rows = cursor.fetchall()
    conn.close()
    
    return [row[0] for row in rows if row[0]]

