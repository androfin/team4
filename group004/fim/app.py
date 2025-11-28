"""Flask web dashboard"""
import os
from flask import Flask, render_template, request, jsonify
from .models import (
    get_latest_events,
    get_latest_events_filtered,
    get_distinct_file_paths,
    get_file_classification,
    upsert_file_classification,
    get_all_classifications,
    get_distinct_endpoints,
    DB_PATH
)
from .mongo_client import is_mongo_connected
from .config import FLASK_HOST, FLASK_PORT

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(ROOT_DIR, "templates")

app = Flask(__name__, template_folder=TEMPLATE_DIR)


@app.route("/")
def index():
    """Main dashboard page with advanced filtering"""
    search_query = request.args.get("search", "").strip()
    
    event_types_param = request.args.get("types", "")
    if event_types_param:
        event_types = [t.strip() for t in event_types_param.split(",") if t.strip()]
        if "all" in event_types and len(event_types) > 1:
            event_types.remove("all")
        elif "all" in event_types:
            event_types = None
    else:
        event_types = None
    
    search_columns_param = request.args.get("columns", "")
    if search_columns_param:
        search_columns = [c.strip() for c in search_columns_param.split(",") if c.strip()]
        if "all" in search_columns:
            search_columns = None
    else:
        search_columns = None
    
    if search_query or (event_types and len(event_types) > 0):
        events = get_latest_events_filtered(
            limit=100,
            event_types=event_types,
            search_query=search_query if search_query else None,
            search_columns=search_columns
        )
    else:
        event_type = request.args.get("type", "all")
        valid_types = ["all", "created", "modified", "deleted"]
        if event_type not in valid_types:
            event_type = "all"
        events = get_latest_events(limit=100, event_type=event_type if event_type != "all" else None)
    
    selected_types = event_types if event_types else []
    if not selected_types:
        selected_type = request.args.get("type", "all")
        if selected_type == "all":
            selected_types = ["all"]
        else:
            selected_types = [selected_type]
    
    has_active_filters = bool(search_query or (event_types and len(event_types) > 0 and event_types != ["all"]))
    
    mongo_status = is_mongo_connected()
    
    return render_template(
        "index.html",
        events=events,
        search_query=search_query,
        selected_event_types=selected_types,
        selected_search_columns=search_columns if search_columns else ["all"],
        has_active_filters=has_active_filters,
        mongo_connected=mongo_status
    )


@app.route("/classification/save-all", methods=["POST"])
def classification_save_all():
    """AJAX endpoint to save all classifications at once"""
    import json
    import sqlite3
    from datetime import datetime
    
    files_json = request.form.get("files")
    if not files_json:
        return jsonify({"success": False, "message": "Missing files parameter"}), 400
    
    try:
        files = json.loads(files_json)
    except json.JSONDecodeError:
        return jsonify({"success": False, "message": "Invalid JSON format"}), 400
    
    if not isinstance(files, list):
        return jsonify({"success": False, "message": "Files must be a list"}), 400
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    saved_count = 0
    for file_data in files:
        file_path = file_data.get("file_path")
        classification = file_data.get("classification", "").strip()
        endpoint = file_data.get("endpoint")
        hostname = file_data.get("hostname")
        username = file_data.get("username")
        
        if not file_path:
            continue
        
        if not classification:
            cursor.execute("DELETE FROM file_classification WHERE file_path = ?", (file_path,))
        else:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            cursor.execute("SELECT id FROM file_classification WHERE file_path = ?", (file_path,))
            existing = cursor.fetchone()
            
            if existing:
                cursor.execute("""
                    UPDATE file_classification SET
                        classification = ?,
                        last_updated_timestamp = ?,
                        endpoint = ?,
                        hostname = ?,
                        username = ?
                    WHERE file_path = ?
                """, (classification, timestamp, endpoint, hostname, username, file_path))
            else:
                cursor.execute("""
                    INSERT INTO file_classification (
                        file_path, classification, last_updated_timestamp,
                        endpoint, hostname, username
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (file_path, classification, timestamp, endpoint, hostname, username))
        
        saved_count += 1
    
    conn.commit()
    conn.close()
    
    return jsonify({
        "success": True,
        "message": f"Successfully saved {saved_count} classification(s)"
    })


@app.route("/classification/update", methods=["POST"])
def classification_update():
    """AJAX endpoint to update classification without page reload"""
    import sqlite3
    
    file_path = request.form.get("file_path")
    classification = request.form.get("classification", "").strip()
    endpoint = request.form.get("endpoint")
    hostname = request.form.get("hostname")
    username = request.form.get("username")
    
    if not file_path:
        return jsonify({"success": False, "message": "Missing file_path parameter"}), 400
    
    if not classification:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM file_classification WHERE file_path = ?", (file_path,))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Classification cleared successfully"})
    
    upsert_file_classification(
        file_path=file_path,
        classification=classification,
        endpoint=endpoint,
        hostname=hostname,
        username=username
    )
    
    return jsonify({"success": True, "message": "Classification updated successfully"})


@app.route("/classification", methods=["GET"])
def classification():
    """Classification page for assigning security levels to files"""
    
    endpoints_param = request.args.get("endpoints", "")
    if endpoints_param:
        selected_endpoints = [e.strip() for e in endpoints_param.split(",") if e.strip()]
    else:
        selected_endpoints = None
    
    search_query = request.args.get("search", "").strip()
    
    files = get_distinct_file_paths(endpoints=selected_endpoints)
    
    if search_query:
        files = [f for f in files if search_query.lower() in f["file_path"].lower()]
    
    classifications_dict = {}
    if selected_endpoints:
        classifications = get_all_classifications(endpoints=selected_endpoints)
    else:
        classifications = get_all_classifications()
    
    for cls in classifications:
        classifications_dict[cls["file_path"]] = cls
    
    for file_info in files:
        file_path = file_info["file_path"]
        if file_path in classifications_dict:
            file_info["classification"] = classifications_dict[file_path]["classification"]
            file_info["classification_id"] = classifications_dict[file_path]["id"]
        else:
            file_info["classification"] = None
            file_info["classification_id"] = None
    
    available_endpoints = get_distinct_endpoints()
    
    return render_template(
        "classification.html",
        files=files,
        available_endpoints=available_endpoints,
        selected_endpoints=selected_endpoints if selected_endpoints else [],
        search_query=search_query
    )


@app.route("/api/status")
def api_status():
    """API endpoint to check system status"""
    return jsonify({
        "status": "running",
        "mongo_connected": is_mongo_connected()
    })


def run_app(host: str = None, port: int = None, debug: bool = False) -> None:
    """Run the Flask application"""
    actual_host = host if host is not None else FLASK_HOST
    actual_port = port if port is not None else FLASK_PORT
    
    print(f"[FLASK] Starting dashboard on http://{actual_host}:{actual_port}")
    app.run(host=actual_host, port=actual_port, debug=debug, use_reloader=False)
