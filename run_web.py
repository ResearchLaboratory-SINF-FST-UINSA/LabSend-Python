"""
LabSend Print Transfer - Simple Runner
Menjalankan aplikasi tanpa perlu compile menjadi EXE
"""

import sys
import os
import subprocess

# Install dependencies if not installed
def install_requirements():
    requirements = [
        'fastapi',
        'uvicorn',
        'jinja2',
        'python-multipart',
        'aiofiles',
        'qrcode',
        'pillow',
        'pystray',
        'pydantic'
    ]

    print("[LabSend] Installing dependencies...")
    for req in requirements:
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', req, '-q'])
            print(f"  ✓ {req}")
        except Exception as e:
            print(f"  ✗ {req}: {e}")
    print("[LabSend] Dependencies installed!")

def main():
    print("\n" + "=" * 60)
    print("  LabSend Print Transfer - Web Version")
    print("=" * 60)
    print()
    print("  Jalankan di browser:")
    print("  • Dashboard: http://localhost:4711/admin")
    print("  • QR Page:   http://localhost:4711/qr")
    print("  • Settings:  http://localhost:4711/settings")
    print()
    print("  Tekan Ctrl+C untuk berhenti")
    print("=" * 60 + "\n")

    # Change to app directory
    app_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(app_dir)

    # Run the main app
    sys.path.insert(0, app_dir)

    from app.config import load_config, ensure_upload_folder
    from app.database import init_database, expire_old_qr_sessions
    from app.qr_service import create_new_qr_session
    from app.server import app

    # Initialize
    print("[LabSend] Initializing...")
    load_config()
    init_database()
    ensure_upload_folder()
    expire_old_qr_sessions()

    qr_data = create_new_qr_session()
    print(f"[LabSend] QR Token: {qr_data['token']}")
    print(f"[LabSend] URL: {qr_data['url']}")
    print()
    print("[LabSend] Starting server...")
    print()

    # Run with uvicorn
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=4711, log_level="info")

if __name__ == "__main__":
    # Try to install dependencies first
    try:
        import fastapi
        print("[LabSend] Dependencies already installed")
    except ImportError:
        print("[LabSend] Installing dependencies...")
        install_requirements()

    try:
        main()
    except KeyboardInterrupt:
        print("\n[LabSend] Dihentikan oleh user")
    except Exception as e:
        print(f"[LabSend] Error: {e}")
        input("\nTekan Enter untuk keluar...")