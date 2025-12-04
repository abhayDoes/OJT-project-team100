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
#diff engine
@app.route("/diff", methods=["POST"])
def diff():
    data = request.json
    A = data.get("id_a")
    B = data.get("id_b")

    conn = get_db()

    def load(id):
        rows = conn.execute(
            "SELECT filepath, hash FROM snapshots WHERE id = ?",
            (id,)
        ).fetchall()
        return {r["filepath"]: r["hash"] for r in rows} if rows else None

    snapA = load(A)
    snapB = load(B)

    if snapA is None or snapB is None:
        return jsonify({"error": "Snapshot ID not found"}), 404

    added = [p for p in snapB if p not in snapA]
    deleted = [p for p in snapA if p not in snapB]
    modified = [p for p in snapB if p in snapA and snapB[p] != snapA[p]]

    return jsonify({
        "summary": {
            "added": len(added),
            "deleted": len(deleted),
            "modified": len(modified)
        },
        "diff_details": {
            "added": added,
            "deleted": deleted,
            "modified": modified
        }
    }), 200


# STATIC

@app.route("/")
def root():
    return send_from_directory(".", "index.html")

@app.route("/<path:path>")
def static_proxy(path):
    return send_from_directory(".", path)

# START

if __name__ == "__main__":
    init_db()
    app.run(port=5503, debug=True)

