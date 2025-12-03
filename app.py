import os
import hashlib
import json
import sqlite3
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)
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
