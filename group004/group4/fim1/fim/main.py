"""Main entry point - runs watcher and Flask dashboard"""
import threading
import time
from .models import init_db
from .watcher import DirectoryWatcher
from .app import run_app
from .config import FLASK_HOST, FLASK_PORT


def main():
    """Initialize and run both the watcher and Flask app"""
    # Initialize database
    print("[INIT] Initializing database...")
    init_db()
    print("[INIT] Database ready")
    
    # Start directory watcher in a background thread
    print("[INIT] Starting directory watcher...")
    watcher = DirectoryWatcher()
    watcher_thread = threading.Thread(target=watcher.start, daemon=True)
    watcher_thread.start()
    
    # Give watcher a moment to start
    time.sleep(0.5)
    
    # Start Flask app (blocking)
    try:
        run_app(host=FLASK_HOST, port=FLASK_PORT, debug=False)
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Shutting down...")
        watcher.stop()


if __name__ == "__main__":
    main()





