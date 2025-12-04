import os
import hashlib
import json
import sqlite3
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)


# --- Database Configuration ---
DATABASE_NAME = os.getenv('DATABASE_NAME', 'snapshots.db')

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row  # Allows accessing columns by name
    return conn

def initialize_database():
    """Creates the necessary table if it doesn't exist."""
    print(f"Initializing database: {DATABASE_NAME}...")
    conn = get_db_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                id TEXT NOT NULL,
                filepath TEXT NOT NULL,
                hash TEXT NOT NULL,
                PRIMARY KEY (id, filepath)
            );
        """)
        conn.commit()
    except Exception as e:
        print(f"Error during database initialization: {e}")
    finally:
        conn.close()

# --- Core Logic Functions ---

def calculate_file_hash(filepath, block_size=65536):
    """Generates a SHA256 hash for the content of a file."""
    if not os.path.exists(filepath) or not os.path.isfile(filepath):
        return None

    hasher = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            buf = f.read(block_size)
            while len(buf) > 0:
                hasher.update(buf)
                buf = f.read(block_size)
        return hasher.hexdigest()
    except Exception as e:
        # Catch PermissionError, read errors, etc.
        print(f"Error reading file {filepath}: {e}")
        return None


def create_snapshot(directory_path, snapshot_id):
    """
    Traverses a directory, calculates file hashes, and saves them to the SQLite database.
    """
    file_contents = {}
    file_count = 0
    full_path = os.path.abspath(directory_path)
            
    if not os.path.isdir(full_path):
        raise FileNotFoundError(f"Directory not found: {full_path}")

    # Traverse the directory and calculate hashes
    for root, _, files in os.walk(full_path):
        for file in files:
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, full_path)
            file_hash = calculate_file_hash(file_path)
            
            if file_hash:
                file_contents[relative_path] = file_hash
                file_count += 1
    
    conn = get_db_connection()
    try:
        # 1. Delete previous snapshot entries with this ID
        conn.execute("DELETE FROM snapshots WHERE id = ?", (snapshot_id,))
        conn.commit()
        
        # 2. Insert new snapshot entries
        snapshot_data = [
            (snapshot_id, path, file_contents[path])
            for path in file_contents
        ]
        conn.executemany(
            "INSERT INTO snapshots (id, filepath, hash) VALUES (?, ?, ?)",
            snapshot_data
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise Exception(f"Database write error: {e}")
    finally:
        conn.close()

    return file_count

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

    
