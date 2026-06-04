"""
LabSend Print Transfer - Configuration Manager
Mengelola konfigurasi aplikasi dari file config.json
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

# Base directories
# BUNDLE_DIR: where bundled read-only assets are (templates, static, assets)
# In one-file mode, PyInstaller extracts them to sys._MEIPASS
if getattr(sys, 'frozen', False):
    BUNDLE_DIR = Path(sys._MEIPASS).resolve()
    # BASE_DIR: writable location next to the exe for config, database, uploads
    BASE_DIR = Path(sys.executable).parent.resolve()
else:
    BUNDLE_DIR = Path(__file__).parent.parent.resolve()
    BASE_DIR = BUNDLE_DIR

DATA_DIR = BASE_DIR / "data"
CONFIG_FILE = DATA_DIR / "config.json"

# Default configuration
DEFAULT_CONFIG = {
    "app_name": "LabSend",
    "lab_name": "Lab Komputer",
    "server_host": "0.0.0.0",
    "server_port": 4711,
    "upload_folder": "data/uploads",
    "qr_expire_seconds": 120,
    "regenerate_qr_after_scan": False,
    "max_file_size_mb": 50,
    "max_total_upload_mb": 200,
    "max_files_per_session": 10,
    "allowed_extensions": [
        "pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx", "jpg", "jpeg", "png"
    ],
    "blocked_extensions": [
        "exe", "msi", "bat", "cmd", "ps1", "vbs", "js", "scr", "com", "dll", "jar", "lnk", "reg"
    ],
    "theme": "system",
    "auto_delete_enabled": True,
    "auto_delete_after_hours": 24,
    "public_base_url": None,
    "app_icon_url": None
}

_config: dict = {}


def load_config() -> dict:
    """Load configuration from config.json, create if not exists."""
    global _config

    # Ensure data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not CONFIG_FILE.exists():
        # Create default config
        _config = DEFAULT_CONFIG.copy()
        save_config(_config)
    else:
        # Load existing config
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                _config = json.load(f)
            # Merge with defaults for any missing keys
            for key, value in DEFAULT_CONFIG.items():
                if key not in _config:
                    _config[key] = value
        except (json.JSONDecodeError, IOError):
            _config = DEFAULT_CONFIG.copy()
            save_config(_config)

    return _config


def save_config(config: dict) -> bool:
    """Save configuration to config.json."""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        global _config
        _config = config
        return True
    except IOError as e:
        print(f"Error saving config: {e}")
        return False


def get_config(key: Optional[str] = None) -> Any:
    """Get config value by key, or all config if key is None."""
    if not _config:
        load_config()

    if key is None:
        return _config.copy()

    return _config.get(key)


def update_config(key: str, value: Any) -> bool:
    """Update a single config value."""
    if not _config:
        load_config()

    _config[key] = value
    return save_config(_config)


def get_upload_folder() -> Path:
    """Get the upload folder path, create if not exists."""
    if not _config:
        load_config()

    folder = BASE_DIR / _config.get("upload_folder", "data/uploads")
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def ensure_upload_folder() -> Path:
    """Ensure upload folder exists."""
    return get_upload_folder()


def get_max_file_size() -> int:
    """Get max file size in bytes."""
    if not _config:
        load_config()
    return _config.get("max_file_size_mb", 50) * 1024 * 1024


def get_max_total_upload() -> int:
    """Get max total upload size in bytes."""
    if not _config:
        load_config()
    return _config.get("max_total_upload_mb", 200) * 1024 * 1024


def get_max_files_per_session() -> int:
    """Get max files per session."""
    if not _config:
        load_config()
    return _config.get("max_files_per_session", 10)


def is_extension_allowed(ext: str) -> bool:
    """Check if file extension is allowed."""
    if not _config:
        load_config()

    ext = ext.lower().lstrip('.')
    allowed = _config.get("allowed_extensions", [])
    blocked = _config.get("blocked_extensions", [])

    if ext in blocked:
        return False

    return ext in allowed


def get_server_url() -> str:
    """Get the server base URL."""
    if not _config:
        load_config()

    public_url = _config.get("public_base_url")
    if public_url:
        return public_url.rstrip('/')

    # For local development/operator access
    host = _config.get("server_host", "0.0.0.0")
    port = _config.get("server_port", 4711)

    if host == "0.0.0.0":
        # Try to get local IP
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            host = s.getsockname()[0]
            s.close()
        except Exception:
            host = "localhost"

    return f"http://{host}:{port}"