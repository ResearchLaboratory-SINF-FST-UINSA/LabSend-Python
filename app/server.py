"""
LabSend Print Transfer - FastAPI Server
Web server utama dengan semua endpoint dan halaman
"""

import os
import json
import asyncio
from pathlib import Path
from typing import Optional
from datetime import datetime

from fastapi import FastAPI, Request, HTTPException, Form, UploadFile, File, Depends
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

from .config import (
    load_config, get_config, save_config, get_upload_folder,
    get_server_url, BASE_DIR, BUNDLE_DIR
)
from .database import (
    init_database, get_all_jobs, get_upload_job,
    get_files_by_job, get_stats, update_job_status, update_file_status,
    get_qr_session_by_token
)
from .qr_service import (
    get_current_qr, regenerate_qr, mark_token_scanned, validate_token
)
from .upload_service import process_upload, get_job_details, reject_job
from .file_service import (
    get_file_info, open_file_with_default_app, open_folder_location,
    open_job_folder, delete_file, format_file_size, get_job_files_list
)
from .print_service import (
    open_file_for_printing, mark_file_printed, mark_job_printed,
    get_available_printers
)
from .firewall_service import (
    setup_firewall_for_lab, check_firewall_rule_exists,
    create_firewall_rule, delete_firewall_rule, get_local_ip,
    get_wifi_name
)
from .cleanup_service import run_cleanup_now, get_storage_stats

# Create FastAPI app
app = FastAPI(
    title="LabSend Print Transfer",
    description="Sistem transfer file untuk print via QR Code",
    version="1.0.0"
)

# Setup templates (use BUNDLE_DIR for bundled assets)
TEMPLATES_DIR = BUNDLE_DIR / "app" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Setup static files (use BUNDLE_DIR for bundled assets)
STATIC_DIR = BUNDLE_DIR / "app" / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ============ Helper Functions ============

def is_localhost(request: Request) -> bool:
    """Check if request is from localhost."""
    client_ip = request.client.host if request.client else ""
    return client_ip in ["127.0.0.1", "localhost", "::1"] or client_ip.startswith("192.168.")


# ============ Root & Health ============

@app.get("/")
async def root():
    """Root page - redirect to admin or QR."""
    return {"message": "LabSend Print Transfer", "version": "1.0.0"}


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "app": "LabSend", "timestamp": datetime.now().isoformat()}


@app.get("/api/token/{token}/status")
async def get_token_status(token: str):
    """Get token status for client-side validation."""
    is_valid, message, session = validate_token(token)
    return {
        "valid": is_valid,
        "message": message,
        "session_id": session['id'] if session else None
    }


@app.get("/api/token/{token}/files")
async def get_token_uploaded_files(token: str):
    """Get uploaded files for a token's session."""
    from .database import get_upload_job, get_files_by_job

    session = get_qr_session_by_token(token)
    if not session:
        return {"files": [], "message": "Token not found"}

    # Find upload jobs for this session
    from .database import get_db_connection
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id FROM upload_jobs
            WHERE qr_session_id = ?
            ORDER BY created_at DESC
            LIMIT 5
        """, (session['id'],))
        jobs = cursor.fetchall()

    result = []
    for job_row in jobs:
        job_id = job_row['id']
        files = get_files_by_job(job_id)
        for f in files:
            result.append({
                "id": f['id'],
                "original_name": f['original_name'],
                "size_bytes": f['size_bytes'],
                "extension": f['extension'],
                "job_id": job_id,
                "status": f['status']
            })

    return {"files": result}


# ============ QR Pages ============

@app.get("/qr", response_class=HTMLResponse)
async def qr_page(request: Request):
    """Fullscreen QR code display page."""
    qr_data = get_current_qr()
    server_url = get_server_url()

    return templates.TemplateResponse("qr.html", {
        "request": request,
        "qr_data": qr_data,
        "server_url": server_url,
        "local_ip": get_local_ip(),
        "wifi_name": get_wifi_name(),
        "config": get_config()
    })


@app.get("/api/qr/current")
async def get_current_qr_api():
    """Get current active QR code."""
    return get_current_qr()


@app.post("/api/qr/regenerate")
async def regenerate_qr_api():
    """Regenerate QR code."""
    return regenerate_qr()


# ============ Upload Pages ============

@app.get("/u/{token}", response_class=HTMLResponse)
async def upload_page(request: Request, token: str):
    """Student upload page."""
    # Mark token as scanned
    mark_token_scanned(token, request.client.host if request.client else None)

    # Get server info
    qr_data = get_current_qr()

    return templates.TemplateResponse("upload.html", {
        "request": request,
        "token": token,
        "qr_data": qr_data,
        "lab_name": get_config("lab_name"),
        "app_name": get_config("app_name"),
        "config": get_config()
    })


@app.post("/api/upload/{token}/identity")
async def submit_identity(token: str, request: Request,
                         student_name: str = Form(...),
                         student_nim: str = Form(...)):
    """Submit student identity and create upload job."""
    # Validate token
    is_valid, message, session = validate_token(token)
    if not is_valid:
        raise HTTPException(status_code=400, detail=message)

    # Create job (identity only, no files yet)
    import uuid
    job_id = str(uuid.uuid4())

    from .database import create_upload_job
    create_upload_job(job_id, session['id'], student_name, student_nim)

    return {
        "job_id": job_id,
        "status": "waiting_upload",
        "message": "Identity validated. Ready for file upload."
    }


@app.post("/api/upload/{token}/files")
async def upload_files(token: str, request: Request,
                      files: list[UploadFile] = File(...),
                      job_id: Optional[str] = Form(None)):
    """Upload files for a job."""
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    # Get identity from job if job_id provided
    student_name = "Unknown"
    student_nim = "Unknown"

    if job_id:
        job = get_upload_job(job_id)
        if job:
            student_name = job['student_name']
            student_nim = job['student_nim']

    # Process upload
    result = await process_upload(
        token=token,
        student_name=student_name,
        student_nim=student_nim,
        files=files,
        client_ip=request.client.host if request.client else None
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))

    return result


# ============ Admin Pages ============

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    """Operator dashboard page."""
    if not is_localhost(request):
        raise HTTPException(status_code=403, detail="Dashboard hanya bisa diakses dari komputer ini")

    qr_data = get_current_qr()
    stats = get_stats()
    jobs = get_all_jobs()
    printers = get_available_printers()

    # Enrich jobs with file info
    for job in jobs:
        job['files'] = get_job_files_list(job['id'])

    return templates.TemplateResponse("admin.html", {
        "request": request,
        "qr_data": qr_data,
        "stats": stats,
        "jobs": jobs,
        "printers": printers,
        "config": get_config(),
        "lab_name": get_config("lab_name"),
        "server_url": get_server_url(),
        "local_ip": get_local_ip()
    })


@app.get("/api/jobs")
async def get_jobs_api(status: Optional[str] = None):
    """Get all jobs."""
    jobs = get_all_jobs(status=status)

    # Add file info
    for job in jobs:
        job['files'] = get_job_files_list(job['id'])

    return {"jobs": jobs}


@app.get("/api/jobs/{job_id}")
async def get_job_api(job_id: str):
    """Get job details."""
    details = get_job_details(job_id)
    if not details:
        raise HTTPException(status_code=404, detail="Job tidak ditemukan")
    return details


# ============ File Actions ============

@app.get("/files/{file_id}/view")
async def view_file(file_id: str, request: Request):
    """View a file inline in browser."""
    if not is_localhost(request):
        raise HTTPException(status_code=403, detail="Akses ditolak")

    file_info = get_file_info(file_id)
    if not file_info:
        raise HTTPException(status_code=404, detail="File tidak ditemukan")

    file_path = file_info['file_path']
    mime_type = file_info['mime_type']
    filename = file_info['original_name']

    # Update viewed status
    from .database import update_file_status
    update_file_status(file_id, 'viewed', 'viewed_at')

    return FileResponse(
        path=file_path,
        media_type=mime_type,
        filename=filename,
        headers={"Content-Disposition": f"inline; filename=\"{filename}\""}
    )


@app.get("/files/{file_id}/download")
async def download_file(file_id: str, request: Request):
    """Download a file."""
    if not is_localhost(request):
        raise HTTPException(status_code=403, detail="Akses ditolak")

    file_info = get_file_info(file_id)
    if not file_info:
        raise HTTPException(status_code=404, detail="File tidak ditemukan")

    file_path = file_info['file_path']
    mime_type = file_info['mime_type']
    filename = file_info['original_name']

    # Update downloaded status
    from .database import update_file_status
    update_file_status(file_id, 'downloaded', 'downloaded_at')

    return FileResponse(
        path=file_path,
        media_type=mime_type,
        filename=filename,
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""}
    )


@app.post("/files/{file_id}/open")
async def open_file(file_id: str, request: Request):
    """Open file with default application."""
    if not is_localhost(request):
        raise HTTPException(status_code=403, detail="Akses ditolak")

    success, message = open_file_for_printing(file_id)
    return {"success": success, "message": message}


@app.post("/files/{file_id}/mark-printed")
async def mark_printed(file_id: str, request: Request):
    """Mark file as printed."""
    if not is_localhost(request):
        raise HTTPException(status_code=403, detail="Akses ditolak")

    success, message = mark_file_printed(file_id)
    return {"success": success, "message": message}


# ============ Bulk File Actions ============

@app.post("/api/files/mark-printed")
async def bulk_mark_printed(request: Request):
    """Mark multiple files as printed."""
    if not is_localhost(request):
        raise HTTPException(status_code=403, detail="Akses ditolak")

    try:
        body = await request.json()
        file_ids = body.get("file_ids", [])

        if not file_ids:
            return {"success": False, "message": "Tidak ada file dipilih"}

        from .database import get_files_by_job, get_upload_job
        from .file_service import get_file_path

        marked_count = 0
        for file_id in file_ids:
            # Get file info
            from .database import get_uploaded_file
            file_record = get_uploaded_file(file_id)
            if not file_record:
                continue

            # Update file status to printed
            from .database import update_file_status
            update_file_status(file_id, 'printed', 'printed_at')
            marked_count += 1

            # Also update job status if needed
            job_id = file_record['job_id']
            job = get_upload_job(job_id)
            if job:
                from .database import update_job_status
                update_job_status(job_id, 'printed')

        return {
            "success": True,
            "message": f"{marked_count} file ditandai sudah dicetak."
        }
    except Exception as e:
        return {"success": False, "message": f"Error: {str(e)}"}


@app.post("/api/files/delete")
async def bulk_delete_files(request: Request):
    """Delete multiple files."""
    if not is_localhost(request):
        raise HTTPException(status_code=403, detail="Akses ditolak")

    try:
        body = await request.json()
        file_ids = body.get("file_ids", [])

        if not file_ids:
            return {"success": False, "message": "Tidak ada file dipilih"}

        from .file_service import delete_file

        deleted_count = 0
        for file_id in file_ids:
            success, message = delete_file(file_id)
            if success:
                deleted_count += 1

        return {
            "success": True,
            "message": f"{deleted_count} file dihapus."
        }
    except Exception as e:
        return {"success": False, "message": f"Error: {str(e)}"}


# ============ Job Actions ============

@app.post("/api/jobs/{job_id}/reject")
async def reject_job_api(job_id: str, request: Request):
    """Reject a job (mark as rejected, keep files for tracking)."""
    if not is_localhost(request):
        raise HTTPException(status_code=403, detail="Akses ditolak")

    success, message = reject_job(job_id)
    return {"success": success, "message": message}


@app.post("/api/jobs/{job_id}/delete")
async def delete_job_api(job_id: str, request: Request):
    """Delete a job completely from database and filesystem."""
    if not is_localhost(request):
        raise HTTPException(status_code=403, detail="Akses ditolak")

    print(f"[API] delete_job called for job_id: {job_id}")
    from .upload_service import hard_delete_job
    success, message = hard_delete_job(job_id)
    print(f"[API] delete_job result: success={success}, message={message}")
    return {"success": success, "message": message}


@app.delete("/api/jobs/{job_id}")
async def delete_job_api_delete(job_id: str, request: Request):
    """Delete a job completely from database and filesystem (RESTful DELETE)."""
    if not is_localhost(request):
        raise HTTPException(status_code=403, detail="Akses ditolak")

    from .upload_service import hard_delete_job
    success, message = hard_delete_job(job_id)
    return {"success": success, "message": message}


@app.get("/api/jobs/{job_id}/details")
async def get_job_details_api(job_id: str, request: Request):
    """Get detailed job information with files."""
    if not is_localhost(request):
        raise HTTPException(status_code=403, detail="Akses ditolak")

    details = get_job_details(job_id)
    if not details:
        raise HTTPException(status_code=404, detail="Job tidak ditemukan")

    return details


@app.post("/api/jobs/{job_id}/print")
async def print_job(job_id: str, request: Request):
    """Mark all files in job as printed."""
    if not is_localhost(request):
        raise HTTPException(status_code=403, detail="Akses ditolak")

    success, message = mark_job_printed(job_id)
    return {"success": success, "message": message}


@app.post("/api/jobs/{job_id}/open-folder")
async def open_job_folder_api(job_id: str, request: Request):
    """Open folder containing job files."""
    if not is_localhost(request):
        raise HTTPException(status_code=403, detail="Akses ditolak")

    success, message = open_job_folder(job_id)
    return {"success": success, "message": message}


# ============ Settings Pages ============

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Settings page."""
    if not is_localhost(request):
        raise HTTPException(status_code=403, detail="Settings hanya bisa diakses dari komputer ini")

    config = get_config()
    storage = get_storage_stats()
    firewall_exists = check_firewall_rule_exists()

    return templates.TemplateResponse("settings.html", {
        "request": request,
        "config": config,
        "storage": storage,
        "firewall_exists": firewall_exists,
        "local_ip": get_local_ip()
    })


@app.get("/api/settings")
async def get_settings_api():
    """Get all settings."""
    return get_config()


@app.post("/api/settings")
async def save_settings_api(request: Request, settings: dict):
    """Save settings."""
    if not is_localhost(request):
        raise HTTPException(status_code=403, detail="Akses ditolak")

    # Allowed keys for saving
    allowed_keys = [
        "app_name", "lab_name", "upload_folder", "theme",
        "public_base_url", "server_host", "server_port",
        "app_icon_url", "max_file_size_mb", "max_total_upload_mb",
        "max_files_per_session", "auto_delete_enabled",
        "auto_delete_after_hours", "allowed_extensions",
        "blocked_extensions"
    ]

    try:
        # Get current config
        current_config = get_config()

        # Update config with new values
        for key, value in settings.items():
            if key in allowed_keys:
                current_config[key] = value

        # Save all at once
        success = save_config(current_config)

        if success:
            return {"success": True, "message": "Settings berhasil disimpan!"}
        else:
            return {"success": False, "message": "Gagal menyimpan settings"}

    except Exception as e:
        return {"success": False, "message": f"Error: {str(e)}"}


@app.post("/api/settings/test-folder")
async def test_folder_api(request: Request, folder: str = Form(...)):
    """Test if folder is writable."""
    if not is_localhost(request):
        raise HTTPException(status_code=403, detail="Akses ditolak")

    try:
        path = Path(folder).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)

        # Test write
        test_file = path / ".write_test"
        test_file.touch()
        test_file.unlink()

        return {"success": True, "message": f"Folder {folder} valid dan writable"}
    except Exception as e:
        return {"success": False, "message": f"Folder tidak valid: {e}"}


@app.post("/api/settings/open-folder")
async def open_settings_folder_api(request: Request):
    """Open the current upload folder."""
    if not is_localhost(request):
        raise HTTPException(status_code=403, detail="Akses ditolak")

    folder = get_upload_folder()
    try:
        os.startfile(str(folder))
        return {"success": True, "message": "Folder terbuka"}
    except Exception as e:
        return {"success": False, "message": f"Error: {e}"}


@app.post("/api/settings/setup-firewall")
async def setup_firewall_api(request: Request):
    """Setup firewall for LabSend."""
    if not is_localhost(request):
        raise HTTPException(status_code=403, detail="Akses ditolak")

    success, message = setup_firewall_for_lab()
    return {"success": success, "message": message}


@app.post("/api/settings/cleanup")
async def run_cleanup_api(request: Request):
    """Run cleanup now."""
    if not is_localhost(request):
        raise HTTPException(status_code=403, detail="Akses ditolak")

    result = run_cleanup_now(force=True)

    # Build detailed message
    parts = []
    if result['jobs'] > 0:
        parts.append(f"{result['jobs']} job")
    if result['files'] > 0:
        parts.append(f"{result['files']} file")
    if result['folders'] > 0:
        parts.append(f"{result['folders']} folder")

    if parts:
        message = f"Dihapus: {', '.join(parts)}"
    else:
        message = "Tidak ada yang perlu dihapus"

    if result['failed'] > 0:
        message += f" ({result['failed']} gagal)"

    return {
        "success": True,
        "deleted_jobs": result['jobs'],
        "deleted_files": result['files'],
        "deleted_folders": result['folders'],
        "failed": result['failed'],
        "message": message
    }


# ============ API - QR Scan ============

@app.post("/api/qr/{token}/scan")
async def scan_qr(token: str, request: Request):
    """Mark QR as scanned."""
    mark_token_scanned(token, request.client.host if request.client else None)
    return {"success": True, "message": "Token discan"}


# ============ Run Server ============

def run_server(host: str = "0.0.0.0", port: int = 4711, reload: bool = False):
    """Run the FastAPI server."""
    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )