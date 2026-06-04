"""
LabSend Print Transfer - Cleanup Service
Menangani penghapusan file lama secara otomatis dan job expired
"""

import shutil
import threading
import time
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from .config import get_config, get_upload_folder, DATABASE_FILE
from .database import (
    get_all_jobs, update_job_status, update_file_status,
    get_files_by_job, get_db_connection
)


def get_old_jobs(hours: int = 24) -> List[Dict[str, Any]]:
    """
    Ambil job-job yang sudah lebih old dari hours.
    Termasuk job yang tidak memiliki file (waiting_upload, expired, dll).

    Returns: list of job records
    """
    cutoff_time = (datetime.now() - timedelta(hours=hours)).isoformat()

    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Find all jobs older than X hours that are not already deleted/rejected
        cursor.execute("""
            SELECT * FROM upload_jobs
            WHERE created_at < ?
            AND status NOT IN ('deleted', 'rejected')
        """, (cutoff_time,))

        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_expired_qr_sessions() -> List[Dict[str, Any]]:
    """
    Ambil QR sessions yang sudah expired.

    Returns: list of QR session records
    """
    now = datetime.now().isoformat()

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM qr_sessions
            WHERE expires_at < ?
            AND status = 'active'
        """, (now,))

        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def delete_job(job: Dict[str, Any], hours: int = 24) -> Dict[str, int]:
    """
    Hapus sebuah job beserta file-file, folder, dan record database.

    Returns: dict dengan count deleted items
    """
    import sqlite3
    from .config import DATABASE_FILE

    job_id = job['id']
    deleted_files = 0
    deleted_folders = 0
    failed_count = 0

    try:
        # Step 1: Get all files for this job from database
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM uploaded_files
                WHERE job_id = ?
            """, (job_id,))
            files = cursor.fetchall()

        # Step 2: Get folder paths to delete
        folder_paths = set()

        # Step 3: Delete each file from disk
        for file_record in files:
            file_path = Path(file_record['file_path'])

            try:
                if file_path.exists():
                    file_path.unlink()
                    deleted_files += 1
                    print(f"[cleanup] Deleted file: {file_path}")

                # Track folder for potential deletion
                folder_paths.add(file_path.parent)

            except Exception as e:
                print(f"[cleanup] Error deleting file {file_record['id']}: {e}")
                failed_count += 1

        # Step 4: Delete job folder if exists
        for folder_path in folder_paths:
            try:
                if folder_path.exists():
                    # Check if folder is empty or contains only hidden files
                    contents = list(folder_path.iterdir())
                    if not contents or all(f.name.startswith('.') for f in contents):
                        for f in contents:
                            try:
                                f.unlink()
                            except:
                                pass
                        folder_path.rmdir()
                        deleted_folders += 1
                        print(f"[cleanup] Deleted empty folder: {folder_path}")
                    else:
                        # Not empty, delete all contents
                        shutil.rmtree(str(folder_path))
                        deleted_folders += 1
                        print(f"[cleanup] Deleted non-empty folder: {folder_path}")

            except Exception as e:
                print(f"[cleanup] Error deleting folder {folder_path}: {e}")
                failed_count += 1

        # Step 5: Delete records from database (PERMANENT DELETE)
        try:
            conn = sqlite3.connect(DATABASE_FILE)
            cursor = conn.cursor()

            # Delete from uploaded_files table
            cursor.execute("DELETE FROM uploaded_files WHERE job_id = ?", (job_id,))
            print(f"[cleanup] Deleted files from uploaded_files for job: {job_id}")

            # Delete from print_jobs table
            cursor.execute("DELETE FROM print_jobs WHERE upload_job_id = ?", (job_id,))
            print(f"[cleanup] Deleted print_jobs for job: {job_id}")

            # Delete from upload_jobs table
            cursor.execute("DELETE FROM upload_jobs WHERE id = ?", (job_id,))
            print(f"[cleanup] Deleted job from upload_jobs: {job_id}")

            conn.commit()
            conn.close()

            # Step 6: Verify deletion
            conn2 = sqlite3.connect(DATABASE_FILE)
            cursor2 = conn2.cursor()
            cursor2.execute("SELECT COUNT(*) as count FROM upload_jobs WHERE id = ?", (job_id,))
            remaining_jobs = cursor2.fetchone()[0]
            cursor2.execute("SELECT COUNT(*) as count FROM uploaded_files WHERE job_id = ?", (job_id,))
            remaining_files = cursor2.fetchone()[0]
            conn2.close()

            print(f"[cleanup] Verification - remaining jobs: {remaining_jobs}, files: {remaining_files}")

            if remaining_jobs > 0 or remaining_files > 0:
                failed_count += 1
                print(f"[cleanup] WARNING: Job not fully deleted from database")

        except Exception as e:
            print(f"[cleanup] Error deleting from database: {e}")
            failed_count += 1

    except Exception as e:
        print(f"[cleanup] Error deleting job {job_id}: {e}")
        failed_count += 1

    return {
        "job_id": job_id,
        "deleted_files": deleted_files,
        "deleted_folders": deleted_folders,
        "failed": failed_count
    }


def cleanup_old_jobs(hours: int = 24) -> Dict[str, Any]:
    """
    Hapus semua job lama beserta file dan foldernya.

    Returns: dict dengan total deleted items
    """
    jobs = get_old_jobs(hours)

    total_deleted_files = 0
    total_deleted_folders = 0
    total_deleted_jobs = 0
    total_failed = 0

    for job in jobs:
        result = delete_job(job, hours)
        total_deleted_files += result['deleted_files']
        total_deleted_folders += result['deleted_folders']
        total_failed += result['failed']
        if result['failed'] == 0:
            total_deleted_jobs += 1

    return {
        "deleted_jobs": total_deleted_jobs,
        "deleted_files": total_deleted_files,
        "deleted_folders": total_deleted_folders,
        "failed": total_failed,
        "total_jobs_checked": len(jobs)
    }


def cleanup_expired_qr_sessions() -> Dict[str, Any]:
    """
    Hapus QR sessions yang sudah expired dan job-job terkait.

    Returns: dict dengan count deleted sessions
    """
    sessions = get_expired_qr_sessions()

    deleted_count = 0

    for session in sessions:
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                # Update session status to expired
                cursor.execute("""
                    UPDATE qr_sessions
                    SET status = 'expired'
                    WHERE id = ?
                """, (session['id'],))
                deleted_count += 1
        except Exception as e:
            print(f"Error expiring QR session {session['id']}: {e}")

    return {
        "deleted_sessions": deleted_count,
        "total_checked": len(sessions)
    }


def cleanup_empty_folders() -> int:
    """
    Hapus folder kosong di dalam upload folder.

    Returns: count of deleted folders
    """
    upload_folder = get_upload_folder()
    deleted_count = 0

    if not upload_folder.exists():
        return 0

    # Walk through all folders (deepest first)
    for folder_path in sorted(upload_folder.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if folder_path.is_dir():
            try:
                contents = list(folder_path.iterdir())
                if not contents or all(f.name.startswith('.') for f in contents):
                    # Delete any files first
                    for f in contents:
                        try:
                            if f.is_file():
                                f.unlink()
                        except:
                            pass
                    folder_path.rmdir()
                    deleted_count += 1
            except Exception:
                pass

    return deleted_count


def get_storage_stats() -> Dict[str, Any]:
    """
    Ambil statistik penyimpanan.

    Returns: dict dengan storage info
    """
    upload_folder = get_upload_folder()

    total_size = 0
    file_count = 0

    if upload_folder.exists():
        for file in upload_folder.rglob("*"):
            if file.is_file():
                total_size += file.stat().st_size
                file_count += 1

    # Get database stats
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) as count,
                   SUM(total_size) as total
            FROM upload_jobs
            WHERE status NOT IN ('deleted', 'rejected')
        """)
        row = cursor.fetchone()

        db_count = row['count'] or 0
        db_total = row['total'] or 0

    return {
        "total_size": total_size,
        "file_count": file_count,
        "total_size_formatted": format_size(total_size),
        "db_job_count": db_count,
        "db_total_size": db_total
    }


def format_size(size_bytes: int) -> str:
    """Format ukuran ke human readable."""
    if size_bytes == 0:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if abs(size_bytes) < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


class CleanupScheduler:
    """Scheduler untuk auto-cleanup job dan file lama."""

    def __init__(self, interval_hours: int = 1):
        self.interval = interval_hours * 3600  # Convert to seconds
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Start the cleanup scheduler."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print(f"[CleanupScheduler] Started with interval: {self.interval} seconds")

    def stop(self):
        """Stop the cleanup scheduler."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self):
        """Run the cleanup loop."""
        while self._running:
            try:
                if get_config("auto_delete_enabled"):
                    hours = get_config("auto_delete_after_hours") or 24

                    # Cleanup old jobs and files
                    result = cleanup_old_jobs(hours)
                    if result['deleted_jobs'] > 0 or result['deleted_files'] > 0:
                        print(f"[CleanupScheduler] Deleted: {result['deleted_jobs']} jobs, {result['deleted_files']} files, {result['deleted_folders']} folders")

                    # Cleanup expired QR sessions
                    cleanup_expired_qr_sessions()

                    # Cleanup empty folders
                    empty_folders = cleanup_empty_folders()
                    if empty_folders > 0:
                        print(f"[CleanupScheduler] Cleaned {empty_folders} empty folders")

            except Exception as e:
                print(f"[CleanupScheduler] Error: {e}")

            # Sleep for interval
            for _ in range(int(self.interval)):
                if not self._running:
                    break
                time.sleep(1)

    def force_run(self, force: bool = False) -> Dict[str, Any]:
        """Force run cleanup now. If force=True, ignores auto_delete_enabled setting."""
        if force or get_config("auto_delete_enabled"):
            hours = get_config("auto_delete_after_hours") or 24

            # Cleanup old jobs and files
            jobs_result = cleanup_old_jobs(hours)

            # Cleanup expired QR sessions
            qr_result = cleanup_expired_qr_sessions()

            # Cleanup empty folders
            empty_folders = cleanup_empty_folders()

            return {
                "jobs": jobs_result['deleted_jobs'],
                "files": jobs_result['deleted_files'],
                "folders": jobs_result['deleted_folders'] + empty_folders,
                "qr_sessions": qr_result['deleted_sessions'],
                "failed": jobs_result['failed']
            }

        return {
            "jobs": 0, "files": 0, "folders": 0, "qr_sessions": 0, "failed": 0
        }


# Global cleanup scheduler instance
_cleanup_scheduler: Optional[CleanupScheduler] = None


def start_cleanup_scheduler():
    """Start the global cleanup scheduler."""
    global _cleanup_scheduler

    if _cleanup_scheduler is None:
        _cleanup_scheduler = CleanupScheduler(interval_hours=1)
        _cleanup_scheduler.start()


def stop_cleanup_scheduler():
    """Stop the global cleanup scheduler."""
    global _cleanup_scheduler

    if _cleanup_scheduler:
        _cleanup_scheduler.stop()
        _cleanup_scheduler = None


def run_cleanup_now(force: bool = False) -> Dict[str, Any]:
    """
    Force run cleanup now.
    If force=True, ignores auto_delete_enabled setting.
    """
    global _cleanup_scheduler

    if _cleanup_scheduler:
        return _cleanup_scheduler.force_run(force=force)

    if force or get_config("auto_delete_enabled"):
        hours = get_config("auto_delete_after_hours") or 24

        jobs_result = cleanup_old_jobs(hours)
        qr_result = cleanup_expired_qr_sessions()
        empty_folders = cleanup_empty_folders()

        return {
            "jobs": jobs_result['deleted_jobs'],
            "files": jobs_result['deleted_files'],
            "folders": jobs_result['deleted_folders'] + empty_folders,
            "qr_sessions": qr_result['deleted_sessions'],
            "failed": jobs_result['failed']
        }

    return {
        "jobs": 0, "files": 0, "folders": 0, "qr_sessions": 0, "failed": 0
    }
