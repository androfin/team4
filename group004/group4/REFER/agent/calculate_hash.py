import hashlib
import json
import os
import socket
import time

from pymongo import MongoClient
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# ============================
# Config & Mongo setup
# ============================

CONFIG_PATH = r"config.json"  # <-- change if needed


def load_config(path: str = CONFIG_PATH) -> dict:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path, "r") as f:
        cfg = json.load(f)

    if "mongo_uri" not in cfg:
        raise ValueError("Config is missing 'mongo_uri'")

    return cfg


config = load_config()

MONGO_URI = config["mongo_uri"]
DB_NAME = config.get("db_name", "fim")
COLLECTION_NAME = config.get("collection_name", "events")
AGENT_ID = config.get("agent_id", socket.gethostname())
WATCH_DIR = config.get("watch_dir", r"C:\Users\Public")

mongo_client = MongoClient(MONGO_URI)
mongo_collection = mongo_client[DB_NAME][COLLECTION_NAME]

# ============================
# Local DB files (JSON)
# ============================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HASH_DB_FILE = os.path.join(BASE_DIR, "hashes.json")
HISTORY_DB_FILE = os.path.join(BASE_DIR, "hash_history.json")


def load_json(path: str):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}


def save_json(obj: dict, path: str):
    with open(path, "w") as f:
        json.dump(obj, f, indent=4)


# ============================
# Helpers: ignore temp files
# ============================

def is_temp_file(path: str) -> bool:
    """Return True if the file should be ignored (e.g., editor temp files)."""
    filename = os.path.basename(path)
    # Only rule requested: skip files ending with "~"
    return filename.endswith("~")


# ============================
# Metadata & hashing (Windows)
# ============================

def get_file_metadata(path: str) -> dict:
    s = os.stat(path, follow_symlinks=False)
    return {
        "size": s.st_size,
        "mtime": int(s.st_mtime),   # last modification time
        "ctime": int(s.st_ctime),   # creation time on Windows
        "readonly": not os.access(path, os.W_OK),
    }


def hash_content(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_state(path: str) -> dict:
    meta = get_file_metadata(path)
    content_hash = hash_content(path)

    state_obj = {
        "path": os.path.abspath(path),
        "content_hash": content_hash,
        "metadata": meta,
    }

    # Stable encoding for state_hash
    state_bytes = json.dumps(state_obj, sort_keys=True,
                             separators=(",", ":")).encode()
    state_hash = hashlib.sha256(state_bytes).hexdigest()

    return {
        "path": state_obj["path"],
        "content_hash": content_hash,
        "metadata": meta,
        "state_hash": state_hash,
    }


# ============================
# History helpers
# ============================

def append_history_entry(state: dict, history_db: dict, timestamp: int):
    """
    Append a state entry to history, but only if the state_hash differs from
    the last recorded one (no duplicate NO_CHANGE entries).
    """
    path = state["path"]
    new_hash = state["state_hash"]

    entry = {
        "timestamp": timestamp,
        "state_hash": new_hash,
        "content_hash": state["content_hash"],
        "metadata": state["metadata"],
    }

    if path not in history_db:
        history_db[path] = [entry]
        return

    last_entry = history_db[path][-1]
    last_hash = last_entry.get("state_hash")

    if last_hash == new_hash:
        # No change in state since last history entry
        return

    history_db[path].append(entry)


def append_deletion_history(path: str, history_db: dict, timestamp: int):
    """
    Append a DELETED event to history, but avoid repeated DELETED entries.
    """
    if path not in history_db:
        history_db[path] = []

    if history_db[path] and history_db[path][-1].get("event") == "DELETED":
        return

    deletion_entry = {
        "timestamp": timestamp,
        "state_hash": None,
        "content_hash": None,
        "metadata": None,
        "event": "DELETED",
    }
    history_db[path].append(deletion_entry)


# ============================
# Mongo event sender
# ============================

def send_event_to_mongo(event: dict):
    """
    Insert a single FIM event document into MongoDB.
    """
    try:
        mongo_collection.insert_one(event)
    except Exception as e:
        # Don't kill the agent if MongoDB is down
        print(f"[!] Failed to send event to MongoDB: {e}")


# ============================
# File system event handler
# ============================

class FIMEventHandler(FileSystemEventHandler):
    def __init__(self, root_dir: str):
        super().__init__()
        self.root_dir = os.path.abspath(root_dir)

    def _handle_file_change(self, path: str, event_type: str):
        # Ignore directories explicitly
        if os.path.isdir(path):
            return

        abs_path = os.path.abspath(path)
        now_ts = int(time.time())

        # Load DBs
        db = load_json(HASH_DB_FILE)
        history_db = load_json(HISTORY_DB_FILE)

        # Handle deletion
        if event_type == "DELETED":
            print(f"[DELETED] {abs_path}")

            # 1. Add to history (single DELETED)
            append_deletion_history(abs_path, history_db, now_ts)

            # 2. Remove from current snapshot DB
            if abs_path in db:
                del db[abs_path]

            # 3. Send deletion event to Mongo
            event_doc = {
                "timestamp": now_ts,
                "event_type": "DELETED",
                "path": abs_path,
                "state_hash": None,
                "content_hash": None,
                "metadata": None,
                "agent_id": AGENT_ID,
            }
            send_event_to_mongo(event_doc)

            # 4. Persist local DBs
            save_json(db, HASH_DB_FILE)
            save_json(history_db, HISTORY_DB_FILE)
            return

        # For CREATED / MODIFIED / MOVED target:
        if not os.path.exists(abs_path):
            # race condition: event fired but file already gone
            return

        # Calculate current state
        try:
            current_state = hash_state(abs_path)
        except (PermissionError, FileNotFoundError):
            # Can't read file for some reason
            return

        old_state = db.get(abs_path)

        if old_state is None:
            # never seen before
            status = "CREATED"
        else:
            # if state_hash is the same, ignore the event (NO_CHANGE)
            if current_state["state_hash"] == old_state.get("state_hash"):
                return
            status = "MODIFIED"

        # Update snapshot & history
        db[abs_path] = current_state
        append_history_entry(current_state, history_db, now_ts)

        # Build and send Mongo event
        event_doc = {
            "timestamp": now_ts,
            "event_type": status,  # CREATED or MODIFIED
            "path": abs_path,
            "state_hash": current_state["state_hash"],
            "content_hash": current_state["content_hash"],
            "metadata": current_state["metadata"],
            "agent_id": AGENT_ID,
        }
        # send_event_to_mongo(event_doc)

        # Save local DBs
        save_json(db, HASH_DB_FILE)
        save_json(history_db, HISTORY_DB_FILE)

        print(f"[{status}] {abs_path}")

    # Watchdog callbacks

    def on_created(self, event):
        if not event.is_directory and not is_temp_file(event.src_path):
            self._handle_file_change(event.src_path, "CREATED")

    def on_modified(self, event):
        if not event.is_directory and not is_temp_file(event.src_path):
            self._handle_file_change(event.src_path, "MODIFIED")

    def on_deleted(self, event):
        if not event.is_directory and not is_temp_file(event.src_path):
            self._handle_file_change(event.src_path, "DELETED")

    def on_moved(self, event):
        if not event.is_directory:
            # source deletion
            if not is_temp_file(event.src_path):
                self._handle_file_change(event.src_path, "DELETED")
            # destination creation
            if not is_temp_file(event.dest_path):
                self._handle_file_change(event.dest_path, "CREATED")


# ============================
# Agent runner
# ============================

def run_agent(watch_dir: str, recursive: bool = True):
    watch_dir = os.path.abspath(watch_dir)
    print(f"[*] Starting FIM agent on: {watch_dir}")
    print(f"[*] Agent ID: {AGENT_ID}")
    print("[*] Press Ctrl+C to stop.\n")

    event_handler = FIMEventHandler(watch_dir)
    observer = Observer()
    observer.schedule(event_handler, watch_dir, recursive=recursive)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[*] Stopping observer...")
        observer.stop()
    observer.join()


if __name__ == "__main__":
    run_agent(WATCH_DIR, recursive=True)
