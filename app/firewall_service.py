"""
LabSend Print Transfer - Firewall Service
Menangani firewall rules untuk mengizinkan akses dari HP mahasiswa
"""

from multipart import multipart
import subprocess
from typing import Tuple, Optional, Dict, Any

from .config import get_config


def check_firewall_rule_exists(rule_name: str = "LabSend Upload Server") -> bool:
    """
    Periksa apakah firewall rule sudah ada.

    Returns: True if rule exists
    """
    try:
        result = subprocess.run(
            ['netsh', 'advfirewall', 'firewall', 'show', 'rule', f'name={rule_name}'],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=0x08000000
        )

        return rule_name in result.stdout
    except Exception as e:
        print(f"Error checking firewall rule: {e}")
        return False


def create_firewall_rule(port: int = 4711,
                          rule_name: str = "LabSend Upload Server") -> Tuple[bool, str]:
    """
    Buat Windows Firewall rule untuk port LabSend.

    Returns: (success, message)
    """
    try:
        # Check if rule already exists
        if check_firewall_rule_exists(rule_name):
            return True, "Firewall rule sudah ada."

        # Create the firewall rule
        result = subprocess.run(
            [
                'netsh', 'advfirewall', 'firewall', 'add', 'rule',
                f'name={rule_name}',
                'dir=in',
                'action=allow',
                'protocol=TCP',
                f'localport={port}',
                'profile=private',
                'enable=yes'
            ],
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=0x08000000
        )

        if result.returncode == 0:
            return True, f"Firewall rule berhasil dibuat untuk port {port}."
        else:
            return False, f"Gagal membuat firewall rule: {result.stderr}"

    except subprocess.TimeoutExpired:
        return False, "Timeout membuat firewall rule."
    except FileNotFoundError:
        return False, "netsh tidak ditemukan. Jalankan sebagai Administrator."
    except Exception as e:
        return False, f"Error membuat firewall rule: {e}"


def delete_firewall_rule(rule_name: str = "LabSend Upload Server") -> Tuple[bool, str]:
    """
    Hapus firewall rule.

    Returns: (success, message)
    """
    try:
        result = subprocess.run(
            ['netsh', 'advfirewall', 'firewall', 'delete', 'rule', f'name={rule_name}'],
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=0x08000000
        )

        if result.returncode == 0:
            return True, f"Firewall rule '{rule_name}' berhasil dihapus."
        else:
            if "no rule" in result.stdout.lower():
                return True, "Firewall rule tidak ditemukan."
            return False, f"Gagal menghapus firewall rule: {result.stderr}"

    except Exception as e:
        return False, f"Error menghapus firewall rule: {e}"


def get_firewall_rule_info(rule_name: str = "LabSend Upload Server") -> Optional[Dict[str, Any]]:
    """
    Ambil informasi firewall rule.

    Returns: dict with rule info or None
    """
    try:
        result = subprocess.run(
            ['netsh', 'advfirewall', 'firewall', 'show', 'rule', f'name={rule_name}', 'verbose'],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=0x08000000
        )

        if rule_name not in result.stdout:
            return None

        info = {
            "name": rule_name,
            "enabled": "Enabled" in result.stdout,
            "direction": "Inbound" if "Dir:In" in result.stdout else "Outbound",
            "action": "Allow" if "Allow" in result.stdout else "Block"
        }

        # Parse port
        if "localport=" in result.stdout:
            start = result.stdout.find("localport=") + len("localport=")
            end = result.stdout.find("\n", start)
            if end == -1:
                end = len(result.stdout)
            info["port"] = result.stdout[start:end].strip()

        return info

    except Exception as e:
        print(f"Error getting firewall rule info: {e}")
        return None


def get_manual_instruction(port: int = 4711) -> str:
    """
    Dapatkan instruksi manual untuk membuka firewall.

    Returns: manual instruction text
    """
    return f"""Untuk membuka firewall secara manual:

1. Buka Windows Defender Firewall with Advanced Security
2. Klik 'Inbound Rules' di panel kiri
3. Klik 'New Rule...' di panel kanan
4. Pilih 'Port' dan klik Next
5. Pilih 'TCP' dan masukkan port {port}, klik Next
6. Pilih 'Allow the connection' dan klik Next
7. Centang 'Private' dan klik Next
8. Beri nama 'LabSend Upload Server' dan klik Finish

Atau jalankan Command Prompt sebagai Administrator dan ketik:
netsh advfirewall firewall add rule name="LabSend Upload Server" dir=in action=allow protocol=TCP localport={port} profile=private enable=yes
"""


def setup_firewall_for_lab() -> Tuple[bool, str]:
    """
    Setup firewall untuk penggunaan di lab.

    Returns: (success, message)
    """
    port = get_config("server_port") or 4711
    success, message = create_firewall_rule(port)

    if not success:
        # Return manual instructions
        return False, f"{message}\n\n{get_manual_instruction(port)}"

    return True, message


def test_network_connectivity(target_ip: str, port: int = 4711) -> Tuple[bool, str]:
    """
    Test apakah port bisa diakses dari luar.

    Returns: (can_connect, message)
    """
    import socket

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((target_ip, port))
        sock.close()

        if result == 0:
            return True, f"Port {port} bisa diakses dari {target_ip}"
        else:
            return False, f"Port {port} tidak bisa diakses. Pastikan firewall sudah dibuka."

    except Exception as e:
        return False, f"Error testing connectivity: {e}"


def get_local_ip() -> str:
    """Dapatkan IP lokal komputer."""
    import socket

    try:
        # Connect to an external address to determine local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip_address = s.getsockname()[0]
        s.close()
        return ip_address
    except Exception:
        return "127.0.0.1"


def get_wifi_name() -> str:
    """Dapatkan nama WiFi yang sedang terhubung."""
    try:
        import subprocess
        result = subprocess.run(
            ['netsh', 'wlan', 'show', 'interfaces'], 
            capture_output=True, 
            text=True,
            creationflags=0x08000000
        )
        for line in result.stdout.split('\n'):
            # Looking for line with " SSID                   : NetworkName"
            if " SSID " in line or (" SSID" in line and "BSSID" not in line):
                parts = line.split(':', 1)
                if len(parts) > 1:
                    return parts[1].strip()
    except Exception:
        pass
    return "LAN / Tidak diketahui"