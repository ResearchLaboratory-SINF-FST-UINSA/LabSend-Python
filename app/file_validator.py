"""
LabSend Print Transfer - File Validator
Validasi file upload: ekstensi, ukuran, karakter berbahaya
"""

import re
import hashlib
from pathlib import Path
from typing import Tuple, Optional

from .config import (
    is_extension_allowed, get_max_file_size, get_max_total_upload,
    get_max_files_per_session
)


def sanitize_filename(filename: str) -> str:
    """
    Sanitasi nama file untuk keamanan.
    - Hapus karakter berbahaya
    - Hapus path traversal (../)
    - Ganti spasi dengan underscore
    - Batasi panjang
    """
    # Hapus karakter berbahaya
    filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', filename)

    # Hapus path traversal
    filename = filename.replace('..', '')
    filename = filename.replace('/', '')
    filename = filename.replace('\\', '')

    # Ganti spasi dengan underscore
    filename = filename.replace(' ', '_')

    # Hapus leading/trailing dots dan spaces
    filename = filename.strip('. ')

    # Batasi panjang (255 char max untuk filesystem)
    if len(filename) > 200:
        name, ext = Path(filename).stem, Path(filename).suffix
        filename = name[:200] + ext

    # Jika nama kosong, gunakan default
    if not filename:
        filename = "unnamed_file"

    return filename


def get_file_extension(filename: str) -> str:
    """Ambil ekstensi file (tanpa titik)."""
    ext = Path(filename).suffix.lower().lstrip('.')
    return ext


def validate_file_extension(filename: str) -> Tuple[bool, str]:
    """
    Validasi ekstensi file.
    Returns: (is_valid, error_message)
    """
    ext = get_file_extension(filename)

    if not ext:
        return False, "File harus memiliki ekstensi."

    if not is_extension_allowed(ext):
        return False, f"Ekstensi .{ext} tidak diizinkan."

    return True, ""


def validate_file_size(size_bytes: int) -> Tuple[bool, str]:
    """
    Validasi ukuran file.
    Returns: (is_valid, error_message)
    """
    max_size = get_max_file_size()

    if size_bytes > max_size:
        max_mb = max_size / (1024 * 1024)
        return False, f"Ukuran file melebihi batas maksimum ({max_mb:.0f} MB)."

    return True, ""


def validate_total_size(total_size_bytes: int) -> Tuple[bool, str]:
    """
    Validasi total ukuran upload.
    Returns: (is_valid, error_message)
    """
    max_total = get_max_total_upload()

    if total_size_bytes > max_total:
        max_mb = max_total / (1024 * 1024)
        return False, f"Total ukuran upload melebihi batas ({max_mb:.0f} MB)."

    return True, ""


def validate_file_count(file_count: int) -> Tuple[bool, str]:
    """
    Validasi jumlah file.
    Returns: (is_valid, error_message)
    """
    max_files = get_max_files_per_session()

    if file_count > max_files:
        return False, f"Jumlah file melebihi batas maksimum ({max_files} file)."

    return True, ""


def validate_file(filename: str, size_bytes: int,
                  current_total: int = 0,
                  current_count: int = 0) -> Tuple[bool, str]:
    """
    Validasi lengkap satu file.
    Returns: (is_valid, error_message)
    """
    # Validasi ekstensi
    valid, msg = validate_file_extension(filename)
    if not valid:
        return False, msg

    # Validasi ukuran file individual
    valid, msg = validate_file_size(size_bytes)
    if not valid:
        return False, msg

    # Validasi total upload
    valid, msg = validate_total_size(current_total + size_bytes)
    if not valid:
        return False, msg

    # Validasi jumlah file
    valid, msg = validate_file_count(current_count + 1)
    if not valid:
        return False, msg

    return True, ""


def get_mime_type(filename: str) -> str:
    """Dapatkan MIME type berdasarkan ekstensi file."""
    ext = get_file_extension(filename)

    mime_types = {
        'pdf': 'application/pdf',
        'doc': 'application/msword',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'ppt': 'application/vnd.ms-powerpoint',
        'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'xls': 'application/vnd.ms-excel',
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
    }

    return mime_types.get(ext, 'application/octet-stream')


def calculate_file_hash(file_path: Path) -> Optional[str]:
    """Hitung SHA256 hash dari file."""
    try:
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    except Exception as e:
        print(f"Error calculating file hash: {e}")
        return None


def validate_path_traversal(path: str) -> bool:
    """Cegah path traversal attack."""
    # Normalisasi path
    normalized = Path(path).as_posix()

    # Cek apakah ada .. atau path absolut yang mencurigakan
    if '..' in path or path.startswith('/') or ':' in path[1:]:
        return False

    return True