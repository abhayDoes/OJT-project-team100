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
