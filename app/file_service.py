"""
LabSend Print Transfer - File Service
Menangani operasi file: view, download, open
"""

import os
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from datetime import datetime

from .config import get_upload_folder
from .database import (
    get_uploaded_file, update_file_status, get_files_by_job,
    get_upload_job
)
from .file_validator import validate_path_traversal


def get_file_path(file_id: str) -> Tuple[bool, str, Optional[Path]]:
    """
    Ambil path file berdasarkan file_id dengan validasi keamanan.

    Returns: (is_valid, message, file_path)
    """
    # Get file from database
    file_record = get_uploaded_file(file_id)

    if not file_record:
        return False, "File tidak ditemukan.", None

    if file_record['status'] == 'deleted':
        return False, "File sudah dihapus.", None

    file_path = Path(file_record['file_path'])

    # Security: Ensure file is within upload folder
    upload_folder = get_upload_folder().resolve()

    try:
        resolved_path = file_path.resolve()

        # Check if file is within upload folder
        if not str(resolved_path).startswith(str(upload_folder)):
            return False, "Akses file ditolak.", None

        if not resolved_path.exists():
            return False, "File tidak ditemukan di sistem.", None

    except Exception as e:
        return False, f"Error mengakses file: {e}", None

    return True, "", file_path


def record_file_viewed(file_id: str) -> bool:
    """Catat bahwa file telah dilihat."""
    return update_file_status(file_id, 'viewed', 'viewed_at')


def record_file_downloaded(file_id: str) -> bool:
    """Catat bahwa file telah diunduh."""
    return update_file_status(file_id, 'downloaded', 'downloaded_at')


def get_file_info(file_id: str) -> Optional[Dict[str, Any]]:
    """Ambil informasi file termasuk metadata untuk response."""
    is_valid, message, file_path = get_file_path(file_id)

    if not is_valid:
        return None

    file_record = get_uploaded_file(file_id)
    if not file_record:
        return None

    return {
        "id": file_record['id'],
        "original_name": file_record['original_name'],
        "stored_name": file_record['stored_name'],
        "file_path": file_path,
        "mime_type": file_record['mime_type'],
        "extension": file_record['extension'],
        "size_bytes": file_record['size_bytes'],
        "created_at": file_record['created_at']
    }


def open_file_with_default_app(file_id: str) -> Tuple[bool, str]:
    """
    Buka file dengan aplikasi default Windows.

    Returns: (success, message)
    """
    is_valid, message, file_path = get_file_path(file_id)

    if not is_valid:
        return False, message

    try:
        # Windows: use start command
        os.startfile(str(file_path))
        # Record that file was opened
        record_file_viewed(file_id)
        return True, "File dibuka dengan aplikasi default."
    except AttributeError:
        # Linux/Mac fallback
        try:
            subprocess.run(['xdg-open', str(file_path)], check=True)
            record_file_viewed(file_id)
            return True, "File dibuka dengan aplikasi default."
        except Exception:
            return False, "Tidak dapat membuka file di platform ini."
    except Exception as e:
        return False, f"Error membuka file: {e}"


def open_folder_location(file_id: str) -> Tuple[bool, str]:
    """
    Buka Windows Explorer di lokasi file.

    Returns: (success, message)
    """
    is_valid, message, file_path = get_file_path(file_id)

    if not is_valid:
        return False, message

    try:
        folder_path = file_path.parent

        # Windows: open folder and select file
        subprocess.run(['explorer', '/select,', str(file_path)], check=True, creationflags=0x08000000)
        return True, f"Folder terbuka: {folder_path}"
    except Exception as e:
        return False, f"Error membuka folder: {e}"


def open_job_folder(job_id: str) -> Tuple[bool, str]:
    """
    Buka folder job di Windows Explorer.

    Returns: (success, message)
    """
    files = get_files_by_job(job_id)

    if not files:
        return False, "Job tidak memiliki file."

    # Get folder from first file
    file_path = Path(files[0]['file_path'])
    folder_path = file_path.parent

    try:
        subprocess.run(['explorer', str(folder_path)], check=True, creationflags=0x08000000)
        return True, f"Folder terbuka: {folder_path}"
    except Exception as e:
        return False, f"Error membuka folder: {e}"


def delete_file(file_id: str) -> Tuple[bool, str]:
    """
    Hapus file dari sistem dan database.

    Returns: (success, message)
    """
    is_valid, message, file_path = get_file_path(file_id)

    if not is_valid:
        return False, message

    try:
        # Delete physical file
        if file_path.exists():
            file_path.unlink()

        # Update database status
        update_file_status(file_id, 'deleted')

        return True, "File berhasil dihapus."
    except Exception as e:
        return False, f"Error menghapus file: {e}"


def format_file_size(size_bytes: int) -> str:
    """Format ukuran file ke human readable string."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def get_job_files_list(job_id: str) -> list:
    """Ambil daftar file untuk sebuah job dengan informasi lengkap."""
    job = get_upload_job(job_id)
    if not job:
        return []

    files = get_files_by_job(job_id)

    return [
        {
            "id": f['id'],
            "original_name": f['original_name'],
            "size_formatted": format_file_size(f['size_bytes']),
            "size_bytes": f['size_bytes'],
            "extension": f['extension'],
            "mime_type": f['mime_type'],
            "status": f['status'],
            "created_at": f['created_at']
        }
        for f in files
    ]