"""Main entry point - runs watcher and Flask dashboard"""
import threading
import time
from .models import init_db
from .watcher import DirectoryWatcher
from .app import run_app
from .config import FLASK_HOST, FLASK_PORT
from .mongo_client import get_mongo_connection


def main():
    """Initialize and run both the watcher and Flask app"""
    print("[INIT] Initializing database...")
    init_db()
    print("[INIT] Database ready")
    
    print("[INIT] Checking MongoDB connection...")
    mongo = get_mongo_connection()
    if mongo is not None:
        print("[INIT] MongoDB connected successfully")
    else:
        print("[INIT] MongoDB not available - events will be stored locally only")
    
    print("[INIT] Starting directory watcher...")
    watcher = DirectoryWatcher()
    watcher_thread = threading.Thread(target=watcher.start, daemon=True)
    watcher_thread.start()
    
    time.sleep(0.5)
    
    try:
        run_app(host=FLASK_HOST, port=FLASK_PORT, debug=False)
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Shutting down...")
        watcher.stop()


if __name__ == "__main__":
    main()
