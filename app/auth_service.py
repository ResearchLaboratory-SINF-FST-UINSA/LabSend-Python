"""
LabSend Print Transfer - Authentication Service
Mengelola autentikasi user dengan JWT tokens
"""

import uuid
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple

from .database import (
    create_user, get_user_by_username, get_user_by_id, get_all_users,
    update_user_login, delete_user, update_user_password, toggle_user_status
)


# JWT Secret - in production, use environment variable
JWT_SECRET = secrets.token_hex(32)
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24


def hash_password(password: str) -> str:
    """Hash password using SHA-256 with salt."""
    salt = secrets.token_hex(16)
    hash_obj = hashlib.sha256((salt + password).encode())
    return f"{salt}${hash_obj.hexdigest()}"


def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against hash."""
    try:
        salt, stored_hash = password_hash.split('$')
        hash_obj = hashlib.sha256((salt + password).encode())
        return hash_obj.hexdigest() == stored_hash
    except ValueError:
        return False


def generate_token() -> str:
    """Generate a secure random token."""
    return secrets.token_urlsafe(32)


def validate_student_nim(student_nim: str) -> bool:
    """Validate NIM format: 11 digits and starts with 09."""
    return bool(student_nim and student_nim.isdigit() and len(student_nim) == 11 and student_nim.startswith('09'))


def create_access_token(user_id: str, username: str, role: str) -> Dict[str, Any]:
    """Create access token for user."""
    token = generate_token()
    expires_at = (datetime.now() + timedelta(hours=JWT_EXPIRY_HOURS)).isoformat()

    return {
        "token": token,
        "user_id": user_id,
        "username": username,
        "role": role,
        "expires_at": expires_at,
        "expires_in": JWT_EXPIRY_HOURS * 3600  # in seconds
    }


def authenticate_user(username: str, password: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Authenticate user with username and password.

    Returns: (success, user_data, error_message)
    """
    user = get_user_by_username(username)

    if not user:
        return False, None, "Username tidak ditemukan"

    if not user.get('is_active', 1):
        return False, None, "Akun nonaktif"

    if not verify_password(password, user['password_hash']):
        return False, None, "Password salah"

    # Update last login
    update_user_login(username)

    # Return user data (without password hash)
    user_data = {
        "id": user['id'],
        "username": user['username'],
        "role": user['role'],
        "student_name": user.get('student_name', ''),
        "student_nim": user.get('student_nim', ''),
        "created_at": user['created_at'],
        "last_login": datetime.now().isoformat()
    }

    return True, user_data, None


def register_user(username: str, password: str, role: str = "user",
                  student_name: str = "", student_nim: str = "") -> Tuple[bool, Optional[str]]:
    """
    Register a new user.

    Returns: (success, user_id or error_message)
    """
    # Check if username already exists
    existing = get_user_by_username(username)
    if existing:
        return False, "Username sudah digunakan"

    # Validate password
    if len(password) < 4:
        return False, "Password minimal 4 karakter"

    # Validate student profile for normal users
    if role == "user":
        if not student_name:
            return False, "Nama mahasiswa wajib diisi"
        if not validate_student_nim(student_nim):
            return False, "NIM harus 11 digit dan diawali dengan 09"

    # Create user
    user_id = str(uuid.uuid4())
    password_hash = hash_password(password)

    if create_user(user_id, username, password_hash, role, student_name, student_nim):
        return True, user_id

    return False, "Gagal membuat user"


def create_default_admin():
    """Create default admin user if none exists."""
    users = get_all_users()
    if not users:
        user_id = str(uuid.uuid4())
        password_hash = hash_password("admin123")
        create_user(user_id, "admin", password_hash, "admin")
        print("[Auth] Default admin created: admin / admin123")


def change_password(user_id: str, old_password: str, new_password: str) -> Tuple[bool, str]:
    """
    Change user's password.

    Returns: (success, message)
    """
    user = get_user_by_id(user_id)
    if not user:
        return False, "User tidak ditemukan"

    # Verify old password
    if not verify_password(old_password, user['password_hash']):
        return False, "Password lama salah"

    # Validate new password
    if len(new_password) < 4:
        return False, "Password baru minimal 4 karakter"

    # Update password
    new_hash = hash_password(new_password)
    if update_user_password(user_id, new_hash):
        return True, "Password berhasil diubah"

    return False, "Gagal mengubah password"


def get_user_info(user_id: str) -> Optional[Dict[str, Any]]:
    """Get user info without password hash."""
    user = get_user_by_id(user_id)
    if not user:
        return None

    return {
        "id": user['id'],
        "username": user['username'],
        "role": user['role'],
        "created_at": user['created_at'],
        "last_login": user.get('last_login'),
        "is_active": user.get('is_active', 1)
    }
