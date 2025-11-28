"""Directory watcher agent using watchdog"""
import os
import time
from datetime import datetime
import socket
import getpass
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from .config import WATCH_DIRECTORY, ENDPOINT_NAME
from .hashing import compute_hash
from .models import insert_event, get_latest_hash
from .alerts import print_alert


def is_temp_file(path: str) -> bool:
    """Check if file should be ignored (editor temp files, etc.)"""
    filename = os.path.basename(path)
    if filename.endswith("~"):
        return True
    if filename.startswith("."):
        return True
    if filename.endswith(".swp") or filename.endswith(".swo"):
        return True
    if filename.endswith(".pyc") or filename.endswith(".pyo"):
        return True
    if "__pycache__" in path:
        return True
    return False


class FIMEventHandler(FileSystemEventHandler):
    """Handler for file system events"""
    
    def __init__(self):
        super().__init__()
        self.hostname = socket.gethostname()
        self.username = getpass.getuser()
        self.endpoint = ENDPOINT_NAME
    
    def _process_event(self, event_type: str, src_path: str, is_directory: bool = False) -> None:
        """Process a file system event"""
        if is_directory:
            return
        
        if is_temp_file(src_path):
            return
        
        file_path = os.path.abspath(src_path)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        hash_before = None
        hash_after = None
        
        if event_type == "created":
            if not os.path.isfile(file_path):
                return
            hash_after = compute_hash(file_path)
        
        elif event_type == "modified":
            if not os.path.isfile(file_path):
                return
            hash_before = get_latest_hash(file_path)
            hash_after = compute_hash(file_path)
            if hash_before == hash_after:
                return
        
        elif event_type == "deleted":
            hash_before = get_latest_hash(file_path)
            hash_after = None
        
        event_data = {
            "event_type": event_type,
            "file_path": file_path,
            "timestamp": timestamp,
            "endpoint": self.endpoint,
            "hostname": self.hostname,
            "username": self.username,
            "hash_before": hash_before,
            "hash_after": hash_after,
        }
        
        insert_event(event_data)
        
        print_alert(
            event_type=event_type,
            file_path=file_path,
            endpoint=self.endpoint,
            hostname=self.hostname,
            username=self.username,
            timestamp=timestamp
        )
    
    def on_created(self, event):
        """Handle file creation events"""
        self._process_event("created", event.src_path, event.is_directory)
    
    def on_modified(self, event):
        """Handle file modification events"""
        self._process_event("modified", event.src_path, event.is_directory)
    
    def on_deleted(self, event):
        """Handle file deletion events"""
        self._process_event("deleted", event.src_path, event.is_directory)
    
    def on_moved(self, event):
        """Handle file move events"""
        if not event.is_directory:
            if not is_temp_file(event.src_path):
                self._process_event("deleted", event.src_path, False)
            if not is_temp_file(event.dest_path):
                self._process_event("created", event.dest_path, False)


class DirectoryWatcher:
    """Directory watcher agent"""
    
    def __init__(self, watch_directory: str = None):
        self.watch_directory = watch_directory or WATCH_DIRECTORY
        self.observer = None
        self.running = False
    
    def start(self) -> None:
        """Start watching the directory"""
        os.makedirs(self.watch_directory, exist_ok=True)
        
        if self.running:
            return
        
        event_handler = FIMEventHandler()
        self.observer = Observer()
        self.observer.schedule(event_handler, self.watch_directory, recursive=True)
        self.observer.start()
        self.running = True
        
        print(f"[WATCHER] Started monitoring: {os.path.abspath(self.watch_directory)}")
    
    def stop(self) -> None:
        """Stop watching the directory"""
        if self.observer and self.running:
            self.observer.stop()
            self.observer.join()
            self.running = False
            print("[WATCHER] Stopped monitoring")


def run_watcher(watch_directory: str = None) -> DirectoryWatcher:
    """Run the directory watcher (blocking)"""
    watcher = DirectoryWatcher(watch_directory)
    watcher.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        watcher.stop()
    
    return watcher
