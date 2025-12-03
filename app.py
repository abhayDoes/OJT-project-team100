import os
import hashlib
import json
import sqlite3
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)


# --- Database Configuration ---
DATABASE_NAME = 'snapshots.db'

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
