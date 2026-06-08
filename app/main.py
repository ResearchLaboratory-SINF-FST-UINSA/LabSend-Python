"""
LabSend Print Transfer - Main Entry Point
Menjalankan server dan system tray
"""

import sys
import os

# Fix for PyInstaller with console=False where stdout/stderr are None
log_file = os.path.join(os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(__file__), 'labsend_error.log')
if sys.stdout is None:
    sys.stdout = open(log_file, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(log_file, "a", encoding="utf-8")

import signal
import threading
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import load_config, get_config, ensure_upload_folder
from app.database import init_database, expire_old_qr_sessions
from app.qr_service import create_new_qr_session, get_current_qr
from app.cleanup_service import start_cleanup_scheduler, stop_cleanup_scheduler
from app.server import app
from app.tray import start_tray, stop_tray, update_tray_tooltip
from app.auth_service import create_default_admin

# Global shutdown flag
_shutdown_event = threading.Event()
_server_instance = None


def signal_handler(signum, frame):
    """Handle Ctrl+C and other termination signals."""
    print("\n[LabSend] Menerima sinyal shutdown...")
    shutdown()


def shutdown():
    """Shutdown the application gracefully."""
    global _shutdown_event, _server_instance

    print("[LabSend] Menutup aplikasi...")

    # Stop the uvicorn server and release port
    if _server_instance:
        _server_instance.should_exit = True
        print("[LabSend] Server dihentikan, port released")

    # Stop cleanup scheduler
    stop_cleanup_scheduler()

    # Stop tray
    stop_tray()

    # Set shutdown flag
    _shutdown_event.set()

    # Exit
    print("[LabSend] Aplikasi ditutup.")
    import os
    os._exit(0)


def initialize_app():
    """Initialize all application components."""
    print("[LabSend] Inisialisasi LabSend Print Transfer...")

    # Load configuration
    load_config()
    print(f"[LabSend] Config loaded")

    # Initialize database
    init_database()
    print(f"[LabSend] Database initialized")

    # Create default admin user if none exists
    create_default_admin()
    print(f"[LabSend] Auth system ready")

    # Ensure upload folder exists
    ensure_upload_folder()
    print(f"[LabSend] Upload folder ready")

    # Expire old QR sessions
    expire_old_qr_sessions()
    print(f"[LabSend] Old QR sessions expired")

    # Create initial QR session
    qr_data = create_new_qr_session()
    print(f"[LabSend] QR created: {qr_data['token']}")
    print(f"[LabSend] URL: {qr_data['url']}")

    return qr_data


def run_server_threaded(host: str, port: int):
    """Run the FastAPI server in a separate thread."""
    import uvicorn

    global _server_instance

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info"
    )
    _server_instance = uvicorn.Server(config)

    # Run until shutdown
    while not _shutdown_event.is_set():
        try:
            _server_instance.run()
        except Exception as e:
            if not _shutdown_event.is_set():
                print(f"[LabSend] Server error: {e}")


def stop_server():
    """Stop the uvicorn server and release the port."""
    global _server_instance
    if _server_instance:
        print("[LabSend] Stopping server...")
        _server_instance.should_exit = True


def main():
    """Main entry point."""
    global _shutdown_event

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Initialize application
        qr_data = initialize_app()

        # Get server config
        host = get_config("server_host") or "0.0.0.0"
        port = get_config("server_port") or 4711

        # Start cleanup scheduler
        start_cleanup_scheduler()
        print("[LabSend] Cleanup scheduler started")

        # Start server in a separate thread
        server_thread = threading.Thread(
            target=run_server_threaded,
            args=(host, port),
            daemon=True
        )
        server_thread.start()
        print(f"[LabSend] Server running on http://{host}:{port}")

        # Start system tray
        start_tray()

        # Update tray with QR info
        update_tray_tooltip(f"Token: {qr_data['token']}")

        print("\n" + "=" * 50)
        print("  LabSend Print Transfer")
        print("=" * 50)
        print(f"  Dashboard: http://localhost:{port}/admin")
        print(f"  QR Page:    http://localhost:{port}/qr")
        print(f"  Settings:   http://localhost:{port}/settings")
        print("=" * 50)
        print("  Klik kanan icon di system tray untuk menu")
        print("  Tekan Ctrl+C untuk keluar")
        print("=" * 50 + "\n")

        # Keep main thread alive
        import time
        while not _shutdown_event.is_set():
            time.sleep(1)

    except Exception as e:
        print(f"[LabSend] Error: {e}")
        import traceback
        traceback.print_exc()
        shutdown()


if __name__ == "__main__":
    # Check if running in console mode (for PyInstaller)
    if getattr(sys, 'frozen', False):
        # Running as compiled exe
        import ctypes
        try:
            ctypes.windll.kernel32.SetConsoleTitleW("LabSend Print Transfer")
        except Exception:
            pass

    main()