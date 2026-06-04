"""
LabSend Print Transfer - Print Service
Menangani operasi print file
"""

import uuid
import os
import subprocess
from pathlib import Path
from typing import Tuple, Optional, Dict, Any

from .database import (
    get_uploaded_file, update_file_status, update_job_status,
    create_print_job, update_print_job, get_upload_job
)
from .file_service import get_file_path, open_file_with_default_app


def get_available_printers() -> list:
    """
    Dapatkan daftar printer yang tersedia di Windows.

    Returns: list of printer names
    """
    try:
        # Windows: use wmic to list printers
        result = subprocess.run(
            ['wmic', 'printer', 'get', 'name'],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=0x08000000
        )

        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            # Skip header line
            printers = [line.strip() for line in lines[1:] if line.strip()]
            return printers
    except Exception as e:
        print(f"Error getting printers: {e}")

    return []


def open_file_for_printing(file_id: str) -> Tuple[bool, str]:
    """
    Buka file untuk print manual.
    Untuk versi MVP, print dilakukan manual oleh operator.

    Returns: (success, message)
    """
    # Get file info
    is_valid, message, file_path = get_file_path(file_id)

    if not is_valid:
        return False, message

    # Open with default app (operator will print manually)
    success, msg = open_file_with_default_app(file_id)

    if success:
        # Record that file was opened for printing
        update_file_status(file_id, 'printed', 'printed_at')

        # Create print job record
        job = get_upload_job(get_uploaded_file(file_id)['job_id'])
        if job:
            print_job_id = str(uuid.uuid4())
            create_print_job(print_job_id, job['id'], file_id)

    return success, msg


def mark_file_printed(file_id: str) -> Tuple[bool, str]:
    """
    Tandai file sudah dicetak.

    Returns: (success, message)
    """
    file_record = get_uploaded_file(file_id)

    if not file_record:
        return False, "File tidak ditemukan."

    # Update file status
    update_file_status(file_id, 'printed', 'printed_at')

    # Update job status if all files are printed
    job_id = file_record['job_id']
    job = get_upload_job(job_id)

    if job:
        update_job_status(job_id, 'printed')

    return True, "File ditandai sudah dicetak."


def mark_job_printed(job_id: str) -> Tuple[bool, str]:
    """
    Tandai semua file dalam job sudah dicetak.

    Returns: (success, message)
    """
    from .database import get_files_by_job

    job = get_upload_job(job_id)
    if not job:
        return False, "Job tidak ditemukan."

    files = get_files_by_job(job_id)

    for file in files:
        if file['status'] != 'printed':
            update_file_status(file['id'], 'printed', 'printed_at')

    update_job_status(job_id, 'printed')

    return True, f"Semua file dalam job ditandai sudah dicetak."


def silent_print_pdf(file_id: str, printer_name: Optional[str] = None) -> Tuple[bool, str]:
    """
    Print PDF secara silent (tanpa dialog).
    Hanya untuk file PDF.

    Returns: (success, message)
    """
    file_record = get_uploaded_file(file_id)

    if not file_record:
        return False, "File tidak ditemukan."

    if file_record['extension'].lower() != 'pdf':
        return False, "Silent print hanya untuk file PDF."

    is_valid, message, file_path = get_file_path(file_id)

    if not is_valid:
        return False, message

    try:
        # Get default printer if not specified
        if not printer_name:
            printers = get_available_printers()
            if printers:
                printer_name = printers[0]
            else:
                return False, "Tidak ada printer tersedia."

        # Windows: use AcroRd32.exe or default PDF reader for silent print
        # This is a simplified approach - in production, use proper PDF library
        print_cmd = [
            'AcroRd32.exe',
            '/t', str(file_path), printer_name
        ]

        result = subprocess.run(
            print_cmd,
            capture_output=True,
            timeout=30,
            creationflags=0x08000000
        )

        if result.returncode == 0:
            update_file_status(file_id, 'printed', 'printed_at')
            return True, f"Print berhasil ke printer: {printer_name}"
        else:
            return False, "Print gagal. Coba buka file dan print manual."

    except FileNotFoundError:
        return False, "Adobe Reader tidak ditemukan. Buka file dan print manual."
    except subprocess.TimeoutExpired:
        return False, "Print timeout. Coba buka file dan print manual."
    except Exception as e:
        return False, f"Error printing: {e}"


def get_print_history(job_id: Optional[str] = None) -> list:
    """
    Ambil riwayat print.

    Args:
        job_id: Jika specified, hanya untuk job ini

    Returns: list of print jobs
    """
    from .database import get_db_connection

    with get_db_connection() as conn:
        cursor = conn.cursor()

        if job_id:
            cursor.execute("""
                SELECT * FROM print_jobs
                WHERE upload_job_id = ?
                ORDER BY requested_at DESC
            """, (job_id,))
        else:
            cursor.execute("""
                SELECT * FROM print_jobs
                ORDER BY requested_at DESC
                LIMIT 100
            """)

        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def cancel_print_job(print_job_id: str) -> Tuple[bool, str]:
    """
    Batalkan print job.

    Returns: (success, message)
    """
    update_print_job(print_job_id, 'cancelled')
    return True, "Print job dibatalkan."