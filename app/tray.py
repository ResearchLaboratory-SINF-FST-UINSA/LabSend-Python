"""
LabSend Print Transfer - System Tray
System tray icon dan menu menggunakan pystray
"""

import os
import webbrowser
import threading
from pathlib import Path
from typing import Optional

try:
    from PIL import Image
    import pystray
except ImportError:
    pystray = None
    Image = None

from .config import get_config, get_server_url, get_upload_folder
from .qr_service import regenerate_qr, get_current_qr
from .firewall_service import get_local_ip


# Global tray instance
_tray = None
_tray_thread = None
_stop_event = threading.Event()


def create_tray_icon():
    """Create the system tray icon."""

    # Create a simple icon image
    try:
        from PIL import Image as PILImage, ImageDraw
        width = 64
        height = 64
        image = PILImage.new('RGB', (width, height), color='#4648d4')
        draw = ImageDraw.Draw(image)

        # Draw a simple "L" shape
        draw.rectangle([8, 8, 24, 56], fill='white')
        draw.rectangle([8, 8, 56, 24], fill='white')
        image = image  # Keep reference for icon
    except Exception:
        # Fallback - will use None, pystray may not show icon
        image = None
        print("Warning: PIL not available for tray icon")

    def on_click(icon, button):
        """Handle tray icon click."""
        from pystray import ButtonType
        if button == ButtonType.left:
            # Open dashboard
            open_dashboard()
        elif button == pystray.ButtonType.right:
            # Update menu
            icon.update_menu()

    menu = pystray.Menu(
        pystray.MenuItem("LabSend", lambda: None, enabled=False),
        pystray.MenuItem("─" * 20, lambda: None, enabled=False),
        pystray.MenuItem(
            "📋 Tampilkan QR",
            lambda: open_qr()
        ),
        pystray.MenuItem(
            "🖥️ Buka Dashboard",
            lambda: open_dashboard()
        ),
        pystray.MenuItem(
            "⚙️ Buka Settings",
            lambda: open_settings()
        ),
        pystray.MenuItem(
            "📁 Buka Folder Upload",
            lambda: open_upload_folder()
        ),
        pystray.MenuItem("─" * 20, lambda: None, enabled=False),
        pystray.MenuItem(
            "🔄 Regenerate QR",
            lambda: do_regenerate_qr()
        ),
        pystray.MenuItem("─" * 20, lambda: None, enabled=False),
        pystray.MenuItem(
            "❌ Keluar",
            lambda: exit_app()
        )
    )

    tray = pystray.Icon(
        "labsend",
        image,
        "LabSend Print Transfer",
        menu
    )

    return tray


def create_icon_from_file():
    """Try to load icon from assets folder."""
    try:
        from .config import BUNDLE_DIR
        icon_path = BUNDLE_DIR / "app" / "assets" / "tray.ico"
        if icon_path.exists():
            return Image.open(icon_path)
    except Exception:
        pass
    return None


def open_dashboard():
    """Open the admin dashboard in browser."""
    url = f"http://localhost:{get_config('server_port') or 4711}/admin"
    webbrowser.open(url)


def open_qr():
    """Open the QR code page in browser."""
    url = f"http://localhost:{get_config('server_port') or 4711}/qr"
    webbrowser.open(url)


def open_settings():
    """Open the settings page in browser."""
    url = f"http://localhost:{get_config('server_port') or 4711}/settings"
    webbrowser.open(url)


def open_upload_folder():
    """Open the upload folder in Windows Explorer."""
    folder = get_upload_folder()
    try:
        os.startfile(str(folder))
    except Exception:
        try:
            webbrowser.open(str(folder))
        except Exception:
            pass


def do_regenerate_qr():
    """Regenerate QR code."""
    regenerate_qr()


def exit_app():
    """Exit the application."""
    global _tray, _stop_event

    print("[Tray] Exit requested...")

    if _tray:
        _tray.stop()

    _stop_event.set()

    # Trigger full shutdown by setting the shutdown event
    # This will stop the server and release the port
    try:
        from app.main import shutdown as main_shutdown
        print("[Tray] Triggering full shutdown...")
        main_shutdown()
    except Exception as e:
        print(f"[Tray] Error during shutdown: {e}")
        # Fallback: force exit
        import os
        os._exit(0)


def run_tray():
    """Run the system tray (blocking)."""
    global _tray

    if not pystray:
        print("Warning: pystray not available. System tray disabled.")
        return

    _tray = create_tray_icon()

    try:
        _tray.run()
    except Exception as e:
        print(f"Tray error: {e}")


def start_tray():
    """Start the system tray in a separate thread."""
    global _tray_thread, _stop_event

    if not pystray:
        print("Warning: pystray not available. System tray disabled.")
        return

    _stop_event.clear()
    _tray_thread = threading.Thread(target=run_tray, daemon=True)
    _tray_thread.start()


def stop_tray():
    """Stop the system tray."""
    global _tray

    if _tray:
        _tray.stop()


def update_tray_tooltip(message: str):
    """Update the tray icon tooltip."""
    global _tray

    if _tray:
        _tray.title = f"LabSend - {message}"


def get_tray_menu_items():
    """Get current tray menu items with updated status."""
    qr_data = get_current_qr()
    port = get_config('server_port') or 4711
    local_ip = get_local_ip()

    items = [
        pystray.MenuItem("LabSend Print Transfer", lambda: None, enabled=False),
        pystray.MenuItem(f"IP: {local_ip}:{port}", lambda: None, enabled=False),
        pystray.MenuItem(f"Token: {qr_data.get('token', 'N/A')}", lambda: None, enabled=False),
        pystray.MenuItem("─" * 20, lambda: None, enabled=False),
        pystray.MenuItem("📋 Tampilkan QR", lambda: open_qr()),
        pystray.MenuItem("🖥️ Buka Dashboard", lambda: open_dashboard()),
        pystray.MenuItem("⚙️ Buka Settings", lambda: open_settings()),
        pystray.MenuItem("📁 Buka Folder Upload", lambda: open_upload_folder()),
        pystray.MenuItem("─" * 20, lambda: None, enabled=False),
        pystray.MenuItem("🔄 Regenerate QR", lambda: do_regenerate_qr()),
        pystray.MenuItem("─" * 20, lambda: None, enabled=False),
        pystray.MenuItem("❌ Keluar", lambda: exit_app()),
    ]

    return items