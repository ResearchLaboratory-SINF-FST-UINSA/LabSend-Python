"""
LabSend Print Transfer - Upload Service
Menangani proses upload file dari mahasiswa
"""

import uuid
import shutil
import aiofiles
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

from .config import get_upload_folder, get_config
from .database import (
    create_upload_job, get_upload_job, update_job_stats,
    create_uploaded_file, get_files_by_job, update_file_status,
    update_qr_session
)
from .qr_service import validate_token, mark_token_used
from .file_validator import (
    sanitize_filename, get_file_extension, validate_file,
    get_mime_type, calculate_file_hash
)


async def save_uploaded_file(file, destination: Path) -> bool:
    """Simpan file yang diupload ke destination path."""
    try:
        async with aiofiles.open(destination, 'wb') as f:
            content = await file.read()
            await f.write(content)
        return True
    except Exception as e:
        print(f"Error saving file: {e}")
        return False


def create_unique_filename(original_name: str, job_folder: Path) -> str:
    """Buat nama file unik, tambahkan angka jika sudah ada."""
    sanitized = sanitize_filename(original_name)
    filename = sanitized
    counter = 1

    while (job_folder / filename).exists():
        name, ext = Path(sanitized).stem, Path(sanitized).suffix
        filename = f"{name}_{counter}{ext}"
        counter += 1

    return filename


async def process_upload(token: str, student_name: str, student_nim: str,
                        files: List, client_ip: Optional[str] = None) -> Dict[str, Any]:
    """
    Proses upload file dari mahasiswa.

    Returns: dict dengan status dan data job
    """
    # Validate token
    is_valid, message, session = validate_token(token)
    if not is_valid:
        return {"success": False, "error": message}

    # Mark token as scanned
    mark_token_used(token)

    # Create upload job
    job_id = str(uuid.uuid4())
    qr_session_id = session['id']

    if not create_upload_job(job_id, qr_session_id, student_name, student_nim):
        return {"success": False, "error": "Gagal membuat job upload."}

    # Create job folder
    upload_folder = get_upload_folder()
    date_str = datetime.now().strftime("%Y-%m-%d")

    # Sanitasi nama untuk folder
    safe_name = sanitize_filename(student_name)
    safe_nim = sanitize_filename(student_nim)

    job_folder = upload_folder / date_str / f"{safe_nim}_{safe_name}_{job_id[:8]}"

    try:
        job_folder.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return {"success": False, "error": f"Gagal membuat folder: {e}"}

    # Track uploaded files
    uploaded_files = []
    total_size = 0
    current_total = 0
    current_count = 0

    # Validate and save each file
    for file in files:
        filename = file.filename
        size = file.size

        # Validate file
        valid, error_msg = validate_file(
            filename, size, current_total, current_count
        )

        if not valid:
            # Skip invalid file but continue with others
            continue

        # Create unique filename
        stored_name = create_unique_filename(filename, job_folder)
        file_path = job_folder / stored_name

        # Save file
        if await save_uploaded_file(file, file_path):
            # Calculate hash
            file_hash = calculate_file_hash(file_path)

            # Get MIME type
            mime_type = get_mime_type(filename)
            ext = get_file_extension(filename)

            # Save to database
            file_id = str(uuid.uuid4())
            create_uploaded_file(
                file_id=file_id,
                job_id=job_id,
                original_name=filename,
                stored_name=stored_name,
                file_path=str(file_path),
                mime_type=mime_type,
                extension=ext,
                size_bytes=size,
                sha256=file_hash
            )

            uploaded_files.append({
                "id": file_id,
                "original_name": filename,
                "stored_name": stored_name,
                "size": size
            })

            total_size += size
            current_total += size
            current_count += 1

    # Update job stats
    if uploaded_files:
        update_job_stats(job_id, len(uploaded_files), total_size)
    else:
        update_file_status(file_id, 'failed')

    return {
        "success": True,
        "job_id": job_id,
        "student_name": student_name,
        "student_nim": student_nim,
        "files_count": len(uploaded_files),
        "total_size": total_size,
        "files": uploaded_files
    }


def get_job_details(job_id: str) -> Optional[Dict[str, Any]]:
    """Ambil detail job beserta file-file-nya."""
    job = get_upload_job(job_id)
    if not job:
        return None

    files = get_files_by_job(job_id)

    return {
        "job": job,
        "files": files
    }


def get_all_jobs_summary() -> List[Dict[str, Any]]:
    """Ambil semua job untuk dashboard."""
    from .database import get_all_jobs

    jobs = get_all_jobs()

    result = []
    for job in jobs:
        files = get_files_by_job(job['id'])
        result.append({
            "job": job,
            "files": files
        })

    return result


def delete_job_files(job_id: str) -> bool:
    """Hapus semua file dari job."""
    job = get_upload_job(job_id)
    if not job:
        return False

    # Get first file to find job folder
    files = get_files_by_job(job_id)
    if not files:
        return False

    # Get job folder from first file
    job_folder = Path(files[0]['file_path']).parent

    # Delete all files
    try:
        if job_folder.exists():
            shutil.rmtree(job_folder)
        return True
    except Exception as e:
        print(f"Error deleting job files: {e}")
        return False


def reject_job(job_id: str) -> tuple:
    """Tolak job dan hapus record serta file-nya."""
    from .database import update_job_status, get_db_connection

    job = get_upload_job(job_id)
    if not job:
        return False, "Job tidak ditemukan"

    # Delete physical files
    delete_job_files(job_id)

    # Update status to rejected
    update_job_status(job_id, 'rejected')

    return True, "Job berhasil ditolak dan dihapus"