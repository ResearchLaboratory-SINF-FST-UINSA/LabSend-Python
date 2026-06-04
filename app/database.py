"""
LabSend Print Transfer - Database Manager
Mengelola SQLite database untuk menyimpan data QR sessions, jobs, dan files
"""

import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
from datetime import datetime

from .config import BASE_DIR, DATA_DIR

# Database path
DATABASE_FILE = DATA_DIR / "labsend.db"


@contextmanager
def get_db_connection():
    """Context manager for database connections."""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database():
    """Initialize database and create tables if not exists."""
    # Ensure data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Create settings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Create qr_sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS qr_sessions (
                id TEXT PRIMARY KEY,
                token TEXT NOT NULL UNIQUE,
                url TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                scanned_at TEXT,
                used_at TEXT,
                client_ip TEXT
            )
        """)

        # Create upload_jobs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS upload_jobs (
                id TEXT PRIMARY KEY,
                qr_session_id TEXT NOT NULL,
                student_name TEXT NOT NULL,
                student_nim TEXT NOT NULL,
                status TEXT NOT NULL,
                total_files INTEGER NOT NULL DEFAULT 0,
                total_size INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                uploaded_at TEXT,
                previewed_at TEXT,
                printed_at TEXT,
                rejected_at TEXT,
                deleted_at TEXT
            )
        """)

        # Create uploaded_files table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS uploaded_files (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                original_name TEXT NOT NULL,
                stored_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                mime_type TEXT,
                extension TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                sha256 TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                viewed_at TEXT,
                downloaded_at TEXT,
                printed_at TEXT
            )
        """)

        # Create print_jobs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS print_jobs (
                id TEXT PRIMARY KEY,
                upload_job_id TEXT NOT NULL,
                file_id TEXT NOT NULL,
                printer_name TEXT,
                status TEXT NOT NULL,
                requested_at TEXT NOT NULL,
                printed_at TEXT,
                error_message TEXT
            )
        """)

        # Create indexes for better query performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_qr_token ON qr_sessions(token)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_qr_status ON qr_sessions(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON upload_jobs(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_job ON uploaded_files(job_id)")


# ============ Settings Functions ============

def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """Get a setting value from the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row['value'] if row else default


def set_setting(key: str, value: str) -> bool:
    """Set a setting value in the database."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO settings (key, value, updated_at)
                VALUES (?, ?, ?)
            """, (key, value, datetime.now().isoformat()))
        return True
    except Exception as e:
        print(f"Error setting value: {e}")
        return False


# ============ QR Session Functions ============

def create_qr_session(session_id: str, token: str, url: str, expires_at: str) -> bool:
    """Create a new QR session."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO qr_sessions (id, token, url, status, created_at, expires_at)
                VALUES (?, ?, ?, 'active', ?, ?)
            """, (session_id, token, url, datetime.now().isoformat(), expires_at))
        return True
    except Exception as e:
        print(f"Error creating QR session: {e}")
        return False


def get_active_qr_session() -> Optional[Dict[str, Any]]:
    """Get the current active QR session."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM qr_sessions
            WHERE status = 'active'
            ORDER BY created_at DESC
            LIMIT 1
        """)
        row = cursor.fetchone()
        return dict(row) if row else None


def get_qr_session_by_token(token: str) -> Optional[Dict[str, Any]]:
    """Get QR session by token."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM qr_sessions WHERE token = ?", (token,))
        row = cursor.fetchone()
        return dict(row) if row else None


def update_qr_session(token: str, status: str, client_ip: Optional[str] = None) -> bool:
    """Update QR session status."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()

            if status == 'scanned':
                cursor.execute("""
                    UPDATE qr_sessions
                    SET status = ?, scanned_at = ?, client_ip = ?
                    WHERE token = ?
                """, (status, now, client_ip, token))
            elif status == 'used':
                cursor.execute("""
                    UPDATE qr_sessions
                    SET status = ?, used_at = ?
                    WHERE token = ?
                """, (status, now, token))
            elif status == 'expired':
                cursor.execute("""
                    UPDATE qr_sessions
                    SET status = ?
                    WHERE token = ?
                """, (status, token))
        return True
    except Exception as e:
        print(f"Error updating QR session: {e}")
        return False


def expire_old_qr_sessions() -> int:
    """Expire QR sessions that have passed their expiry time. Returns count of expired sessions."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute("""
            UPDATE qr_sessions
            SET status = 'expired'
            WHERE status = 'active' AND expires_at < ?
        """, (now,))
        return cursor.rowcount


# ============ Upload Job Functions ============

def create_upload_job(job_id: str, qr_session_id: str, student_name: str,
                       student_nim: str) -> bool:
    """Create a new upload job."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO upload_jobs (id, qr_session_id, student_name, student_nim, status, created_at)
                VALUES (?, ?, ?, ?, 'waiting_upload', ?)
            """, (job_id, qr_session_id, student_name, student_nim, datetime.now().isoformat()))
        return True
    except Exception as e:
        print(f"Error creating upload job: {e}")
        return False


def get_upload_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Get upload job by ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM upload_jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_all_jobs(status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """Get all upload jobs, optionally filtered by status."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if status:
            cursor.execute("""
                SELECT * FROM upload_jobs
                WHERE status = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (status, limit))
        else:
            cursor.execute("""
                SELECT * FROM upload_jobs
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def update_job_status(job_id: str, status: str) -> bool:
    """Update job status."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute(f"""
                UPDATE upload_jobs
                SET status = ?, {status}_at = ?
                WHERE id = ?
            """, (status, now, job_id))
        return True
    except Exception as e:
        print(f"Error updating job status: {e}")
        return False


def update_job_stats(job_id: str, total_files: int, total_size: int) -> bool:
    """Update job file count and total size."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE upload_jobs
                SET total_files = ?, total_size = ?, status = 'uploaded', uploaded_at = ?
                WHERE id = ?
            """, (total_files, total_size, datetime.now().isoformat(), job_id))
        return True
    except Exception as e:
        print(f"Error updating job stats: {e}")
        return False


# ============ Uploaded File Functions ============

def create_uploaded_file(file_id: str, job_id: str, original_name: str,
                         stored_name: str, file_path: str, mime_type: Optional[str],
                         extension: str, size_bytes: int, sha256: Optional[str] = None) -> bool:
    """Create a new uploaded file record."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO uploaded_files
                (id, job_id, original_name, stored_name, file_path, mime_type, extension,
                 size_bytes, sha256, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)
            """, (file_id, job_id, original_name, stored_name, file_path, mime_type,
                  extension, size_bytes, sha256, datetime.now().isoformat()))
        return True
    except Exception as e:
        print(f"Error creating uploaded file: {e}")
        return False


def get_uploaded_file(file_id: str) -> Optional[Dict[str, Any]]:
    """Get uploaded file by ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM uploaded_files WHERE id = ?", (file_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_files_by_job(job_id: str) -> List[Dict[str, Any]]:
    """Get all files for a job."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM uploaded_files
            WHERE job_id = ?
            ORDER BY created_at ASC
        """, (job_id,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def update_file_status(file_id: str, status: str, timestamp_field: Optional[str] = None) -> bool:
    """Update file status and optionally set a timestamp field."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()

            if timestamp_field:
                cursor.execute(f"""
                    UPDATE uploaded_files
                    SET status = ?, {timestamp_field} = ?
                    WHERE id = ?
                """, (status, now, file_id))
            else:
                cursor.execute("""
                    UPDATE uploaded_files
                    SET status = ?
                    WHERE id = ?
                """, (status, file_id))
        return True
    except Exception as e:
        print(f"Error updating file status: {e}")
        return False


# ============ Print Job Functions ============

def create_print_job(print_job_id: str, upload_job_id: str, file_id: str) -> bool:
    """Create a new print job."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO print_jobs (id, upload_job_id, file_id, status, requested_at)
                VALUES (?, ?, ?, 'requested', ?)
            """, (print_job_id, upload_job_id, file_id, datetime.now().isoformat()))
        return True
    except Exception as e:
        print(f"Error creating print job: {e}")
        return False


def update_print_job(print_job_id: str, status: str, error_message: Optional[str] = None) -> bool:
    """Update print job status."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()

            if status == 'completed':
                cursor.execute("""
                    UPDATE print_jobs
                    SET status = ?, printed_at = ?
                    WHERE id = ?
                """, (status, now, print_job_id))
            else:
                cursor.execute("""
                    UPDATE print_jobs
                    SET status = ?, error_message = ?
                    WHERE id = ?
                """, (status, error_message, print_job_id))
        return True
    except Exception as e:
        print(f"Error updating print job: {e}")
        return False


# ============ Statistics Functions ============

def get_stats() -> Dict[str, Any]:
    """Get dashboard statistics."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Total active queue
        cursor.execute("""
            SELECT COUNT(*) as count FROM upload_jobs
            WHERE status IN ('waiting_upload', 'uploaded', 'waiting_preview')
        """)
        queue_count = cursor.fetchone()['count']

        # Total size transferred
        cursor.execute("SELECT SUM(total_size) as total FROM upload_jobs")
        total_size = cursor.fetchone()['total'] or 0

        # Jobs by status
        cursor.execute("""
            SELECT status, COUNT(*) as count FROM upload_jobs
            GROUP BY status
        """)
        status_counts = {row['status']: row['count'] for row in cursor.fetchall()}

        return {
            "queue_count": queue_count,
            "total_size": total_size,
            "status_counts": status_counts
        }