# File Integrity Monitoring (FIM) System

## Overview
A cybersecurity File Integrity Monitoring system that monitors directories for file changes, calculates SHA256 hashes, compares with baselines, and stores security events both locally (SQLite) and in MongoDB for enterprise-grade security monitoring.

## Current State
- **Status**: Ready for use
- **Last Updated**: November 28, 2025

## Features
- Real-time directory monitoring using watchdog
- SHA256 hash computation for file integrity verification
- Hash comparison with baseline for detecting unauthorized changes
- SQLite database for local event storage
- MongoDB integration for centralized security monitoring
- Flask web dashboard with filtering and hash inspection
- File classification system (Top Secret, Secret, Confidential, Unclassified)
- Console alerts for file system events

## Workflow
```
File Change Detected → File System Monitor → Detect Change Type → 
Analyze File Integrity → Calculate Hash → Compare with Baseline → 
Log Event (Created/Modified/Deleted) → Store in MongoDB → 
Generate Security Alert
```

## Project Structure
```
.
├── main.py                 # Entry point
├── fim/                    # Core FIM module
│   ├── __init__.py
│   ├── config.py          # Configuration settings
│   ├── watcher.py         # Directory watcher agent
│   ├── hashing.py         # SHA256 utilities
│   ├── models.py          # Database layer (SQLite + MongoDB sync)
│   ├── mongo_client.py    # MongoDB client
│   ├── alerts.py          # Console alert logic
│   ├── app.py             # Flask application
│   └── main.py            # Module entry point
├── templates/             # HTML templates
│   ├── base.html
│   ├── index.html         # Dashboard
│   └── classification.html # File classification page
├── watched/               # Directory being monitored
├── data/                  # SQLite database storage
└── group4/               # Original source code (reference)
```

## Configuration

### Environment Variables
- `MONGODB_URI`: MongoDB connection string (stored as secret)
- `MONGO_DB_NAME`: Database name (default: "fim")
- `MONGO_COLLECTION_NAME`: Collection name (default: "events")
- `ENDPOINT_NAME`: Agent endpoint identifier (default: "replit_agent")

### Watched Directory
By default, the system monitors the `./watched` directory. Files created, modified, or deleted in this directory will generate security events.

## Running the Application
```bash
python main.py
```

This will:
1. Initialize the SQLite database
2. Connect to MongoDB (if configured)
3. Start the directory watcher
4. Launch the Flask dashboard on port 5000

## Dashboard Features
- **Events Dashboard**: View all file system events with filtering
- **Hash Inspection**: View before/after hashes for each event
- **Classification Page**: Assign security classifications to files
- **MongoDB Status**: Real-time connection status indicator

## Security Event Types
- **CREATED**: New file detected
- **MODIFIED**: Existing file content changed (hash mismatch)
- **DELETED**: File removed from monitored directory

## Database Schema

### Events Table (SQLite)
- `id`: Auto-incrementing primary key
- `event_type`: created / modified / deleted
- `file_path`: Absolute path to the file
- `timestamp`: Local time string
- `endpoint`: Endpoint identifier
- `hostname`: System hostname
- `username`: Current user
- `hash_before`: Previous hash (for modified/deleted)
- `hash_after`: New hash (for created/modified)
- `synced_to_mongo`: Sync status flag

### MongoDB Document Structure
```json
{
  "timestamp": "2025-11-28 12:00:00",
  "event_type": "MODIFIED",
  "path": "/path/to/file",
  "content_hash": "sha256...",
  "hash_before": "sha256...",
  "hash_after": "sha256...",
  "agent_id": "replit_agent",
  "endpoint": "replit_agent",
  "hostname": "hostname",
  "username": "user"
}
```

## User Preferences
- Security-focused monitoring dashboard
- Real-time file change detection
- Hash-based integrity verification
- MongoDB integration for centralized logging
