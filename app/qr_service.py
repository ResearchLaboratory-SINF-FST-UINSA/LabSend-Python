"""
LabSend Print Transfer - QR Service
Mengelola pembuatan QR code, token, dan session
"""

import uuid
import io
import base64
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple

import qrcode
from qrcode.constants import ERROR_CORRECT_H

from .config import get_config, get_server_url
from .database import (
    create_qr_session, get_active_qr_session, get_qr_session_by_token,
    update_qr_session, expire_old_qr_sessions
)


def generate_token() -> str:
    """Generate unique token."""
    return uuid.uuid4().hex[:16].upper()


def generate_qr_code(url: str, dark_mode: bool = False) -> str:
    """
    Generate QR code as base64 PNG.

    Args:
        url: URL to encode
        dark_mode: Use dark mode colors

    Returns:
        Base64 data URL of QR code image
    """
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    if dark_mode:
        img = qr.make_image(fill_color="white", back_color="#0f172a")
    else:
        img = qr.make_image(fill_color="#1e293b", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    img_base64 = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{img_base64}"


def create_new_qr_session(dark_mode: bool = False) -> Dict[str, Any]:
    """Create new QR session."""
    expire_old_qr_sessions()

    token = generate_token()
    base_url = get_server_url()
    url = f"{base_url}/u/{token}"

    expire_seconds = get_config("qr_expire_seconds") or 120
    expires_at = (datetime.now() + timedelta(seconds=expire_seconds)).isoformat()
    session_id = str(uuid.uuid4())

    create_qr_session(session_id, token, url, expires_at)

    qr_image = generate_qr_code(url, dark_mode=dark_mode)

    return {
        "session_id": session_id,
        "token": token,
        "url": url,
        "expires_at": expires_at,
        "qr_image": qr_image,
        "expires_in": expire_seconds,
        "dark_mode": dark_mode
    }


def get_current_qr(dark_mode: bool = False) -> Dict[str, Any]:
    """Get active QR session."""
    session = get_active_qr_session()

    if not session:
        return create_new_qr_session(dark_mode=dark_mode)

    expires_at = datetime.fromisoformat(session['expires_at'])
    if expires_at < datetime.now():
        update_qr_session(session['token'], 'expired')
        return create_new_qr_session(dark_mode=dark_mode)

    url = f"{get_server_url()}/u/{session['token']}"
    qr_image = generate_qr_code(url, dark_mode=dark_mode)
    remaining = int((expires_at - datetime.now()).total_seconds())

    return {
        "session_id": session['id'],
        "token": session['token'],
        "url": url,
        "expires_at": session['expires_at'],
        "qr_image": qr_image,
        "expires_in": remaining,
        "dark_mode": dark_mode
    }


def validate_token(token: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """Validate token."""
    session = get_qr_session_by_token(token)

    if not session:
        return False, "Token tidak valid.", None

    if session['status'] == 'used':
        return False, "Token sudah digunakan.", None

    if session['status'] not in ('active', 'scanned'):
        return False, f"Token berstatus '{session['status']}'.", None

    expires_at = datetime.fromisoformat(session['expires_at'])
    if expires_at < datetime.now():
        update_qr_session(token, 'expired')
        return False, "Token kadaluarsa.", None

    return True, "Token valid.", session


def mark_token_scanned(token: str, client_ip: Optional[str] = None):
    """Mark token as scanned."""
    update_qr_session(token, 'scanned', client_ip)


def mark_token_used(token: str):
    """Mark token as used."""
    update_qr_session(token, 'used')


def regenerate_qr(dark_mode: bool = False) -> Dict[str, Any]:
    """Force regenerate QR code."""
    current = get_active_qr_session()
    if current:
        update_qr_session(current['token'], 'revoked')
    return create_new_qr_session(dark_mode=dark_mode)


def scan_qr(token: str, client_ip: str = None) -> Dict[str, Any]:
    """Mark QR as scanned from QR scan action."""
    mark_token_scanned(token, client_ip)
    return {"success": True, "message": "Token discan"}
