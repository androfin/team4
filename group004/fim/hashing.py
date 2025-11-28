"""SHA256 hashing utilities"""
import hashlib
import os
from typing import Optional


def compute_hash(file_path: str) -> Optional[str]:
    """Compute SHA256 hash of a file
    
    Args:
        file_path: Path to the file
    
    Returns:
        Hex digest of SHA256 hash, or None if file cannot be read
    """
    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        return None
    
    try:
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(8192), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except (IOError, OSError, PermissionError):
        return None


def get_file_metadata(path: str) -> dict:
    """Get file metadata
    
    Args:
        path: Path to the file
    
    Returns:
        Dictionary with file metadata
    """
    try:
        s = os.stat(path, follow_symlinks=False)
        return {
            "size": s.st_size,
            "mtime": int(s.st_mtime),
            "ctime": int(s.st_ctime),
            "readonly": not os.access(path, os.W_OK),
        }
    except (IOError, OSError, PermissionError):
        return {}


def hash_state(path: str) -> Optional[dict]:
    """Calculate complete file state including hash and metadata
    
    Args:
        path: Path to the file
    
    Returns:
        Dictionary with path, content_hash, metadata, and state_hash
    """
    import json
    
    if not os.path.exists(path) or not os.path.isfile(path):
        return None
    
    try:
        meta = get_file_metadata(path)
        content_hash = compute_hash(path)
        
        if content_hash is None:
            return None
        
        state_obj = {
            "path": os.path.abspath(path),
            "content_hash": content_hash,
            "metadata": meta,
        }
        
        state_bytes = json.dumps(state_obj, sort_keys=True, separators=(",", ":")).encode()
        state_hash = hashlib.sha256(state_bytes).hexdigest()
        
        return {
            "path": state_obj["path"],
            "content_hash": content_hash,
            "metadata": meta,
            "state_hash": state_hash,
        }
    except (IOError, OSError, PermissionError):
        return None
