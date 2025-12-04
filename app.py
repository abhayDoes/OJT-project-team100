import os
import hashlib
import json
import sqlite3
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import tempfile

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

DB_NAME = "snapshots.db"
# --- Database Configuration ---
def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id TEXT NOT NULL,
            filepath TEXT NOT NULL,
            hash TEXT NOT NULL,
            PRIMARY KEY (id, filepath)
        );
    """)
    conn.commit()
    conn.close()





# --- Core Logic Functions ---
def hash_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

#snapshot engine


def build_snapshot(dir_root, snapshot_id):
    conn = get_db()
    conn.execute("DELETE FROM snapshots WHERE id = ?", (snapshot_id,))
    conn.commit()

    count = 0

    for root, _, files in os.walk(dir_root):
        for filename in files:
            full = os.path.join(root, filename)
            rel = os.path.relpath(full, dir_root)
            file_hash = hash_file(full)

            conn.execute(
                "INSERT INTO snapshots(id, filepath, hash) VALUES (?, ?, ?)",
                (snapshot_id, rel, file_hash)
            )
            count += 1

    conn.commit()
    conn.close()
    return count

#Folder upload route
@app.route("/snapshot/upload-folder", methods=["POST"])
def upload_folder():
    snapshot_id = request.form.get("id")
    files = request.files.getlist("files[]")

    if not snapshot_id:
        return jsonify({"error": "Snapshot ID missing"}), 400

    if not files:
        return jsonify({"error": "No files were uploaded"}), 400

    with tempfile.TemporaryDirectory() as tmp:
        # Rebuild folder structure
        for file in files:
            rel = file.filename  # webkitRelativePath
            dest = os.path.join(tmp, rel)

            os.makedirs(os.path.dirname(dest), exist_ok=True)
            file.save(dest)

        count = build_snapshot(tmp, snapshot_id)

    return jsonify({"status": "success", "id": snapshot_id, "file_count": count}), 200

def load_snapshot(snapshot_id):
    """Loads a snapshot from the SQLite database into a dictionary."""
    conn = get_db_connection()
    snapshot = {}
    try:
        cursor = conn.execute("SELECT filepath, hash FROM snapshots WHERE id = ?", (snapshot_id,))
        rows = cursor.fetchall()
        if not rows:
            return None # Snapshot ID not found
            
        for row in rows:
            snapshot[row['filepath']] = row['hash']
        return snapshot
    finally:
        conn.close()


def compare_snapshots(snapshot_a_id, snapshot_b_id):
    """Compares two stored snapshots (A vs B) retrieved from the database."""
    snap_a = load_snapshot(snapshot_a_id)
    snap_b = load_snapshot(snapshot_b_id)

    if snap_a is None or snap_b is None:
        raise ValueError("One or both snapshot IDs not found.")

    added = []
    deleted = []
    modified = []

    # Iterate over Snapshot B (the newer state)
    for path_b, hash_b in snap_b.items():
        if path_b not in snap_a:
            added.append(path_b)
        elif snap_a[path_b] != hash_b:
            modified.append(path_b)

    # Iterate over Snapshot A (the older state) to find deletions
    for path_a in snap_a.keys():
        if path_a not in snap_b:
            deleted.append(path_a)

    return {
        "summary": {
            "added": len(added),
            "deleted": len(deleted),
            "modified": len(modified),
        },
        "diff_details": {
            "added": added,
            "deleted": deleted,
            "modified": modified,
        }
    }


#Flask endpoints

@app.route('/snapshot', methods=['POST'])
def handle_snapshot():
    """Endpoint to create a new file system snapshot."""
    data = request.json
    path = data.get('path')
    snapshot_id = data.get('id')

    if not path or not snapshot_id:
        return jsonify({"error": "Missing 'path' or 'id' in request"}), 400

    try:
        file_count = create_snapshot(path, snapshot_id)
        return jsonify({
            "status": "success",
            "id": snapshot_id,
            "file_count": file_count
        }), 200
    except (FileNotFoundError, PermissionError, Exception) as e:
        # Catch all relevant exceptions
        print(f"Server error during snapshot: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/diff', methods=['POST'])
def handle_diff():
    """Endpoint to compare two existing snapshots."""
    data = request.json
    id_a = data.get('id_a')
    id_b = data.get('id_b')

    if not id_a or not id_b:
        return jsonify({"error": "Missing 'id_a' or 'id_b' in request"}), 400
    
    # Check if snapshots exist before attempting comparison
    if load_snapshot(id_a) is None or load_snapshot(id_b) is None:
        return jsonify({"error": "One or both snapshot IDs do not exist in the database. Please capture them first."}), 404

    try:
        diff_result = compare_snapshots(id_a, id_b)
        return jsonify(diff_result), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        print(f"Server error during diff: {e}")
        return jsonify({"error": "Internal server error during snapshot comparison."}), 500


@app.route('/api/status', methods=['GET'])
def server_status():
    """Simple status check for the frontend, showing stored IDs."""
    conn = get_db_connection()
    try:
        cursor = conn.execute("SELECT DISTINCT id FROM snapshots")
        snapshots = [row[0] for row in cursor.fetchall()]
        return jsonify({
            "status": "Server running", 
            "info": "Snapshot & Diff Backend active with SQLite persistence.",
            "snapshots_in_db": snapshots,
        }), 200
    finally:
        conn.close()

@app.route('/')
def serve_index():
    """Serve the index.html file."""
    return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    """Serve static files (CSS, JS, HTML)."""
    return send_from_directory('.', filename)

if __name__ == '__main__':
    initialize_database()
    print("------------------------------------------------------------------")
    # Render provides PORT as environment variable
    port = int(os.getenv('PORT', 5503))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug, use_reloader=False)

    
