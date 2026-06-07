# LabSend Print Transfer

Aplikasi transfer file untuk print via QR Code berbasis web. Dibuat dengan Python + FastAPI untuk kemudahan penggunaan di laboratorium komputer.

## Cara Menjalankan (Tanpa EXE)

### Metode 1: Double-Click (Paling Mudah)

1. **Double-click file `run.bat`** di folder `labsend`
2. Tunggu sampai server started
3. Buka browser dan akses:
   - **Dashboard**: http://localhost:4711/admin
   - **QR Page**: http://localhost:4711/qr
   - **Settings**: http://localhost:4711/settings

### Metode 2: Via Python Langsung

```bash
cd labsend
python run_web.py
```

### Metode 3: Via uvicorn

```bash
cd labsend
uvicorn app.server:app --host 0.0.0.0 --port 4711 --reload
```

## Fitur Utama

- **QR Code Upload** - Mahasiswa scan QR untuk upload file
- **Multi-file Upload** - Mendukung upload banyak file sekaligus
- **Dashboard Operator** - Kelola file masuk dengan mudah
- **Preview & Print** - Lihat dan print file dengan satu klik
- **Auto-cleanup** - File lama dihapus otomatis
- **Custom Storage** - Simpan di drive lain (D:\, E:\, dll)

## Requirements

- Python 3.11 atau 3.12
- Windows 10/11

## Instalasi

### 1. Persiapan - Install Python

Download dan install Python dari https://www.python.org/downloads/
Pastikan centang **"Add Python to PATH"** saat instalasi.

### 2. Jalankan Aplikasi

```bash
cd labsend
double-click run.bat
```

Atau via command line:

```bash
cd labsend
python run_web.py
```

### 3. Selesai!

Aplikasi akan berjalan dan bisa diakses di browser.

## Penggunaan

### Untuk Operator

1. Jalankan `run.bat` atau `python run_web.py`
2. Buka dashboard di browser: `http://localhost:4711/admin`
3. Tampilkan QR ke mahasiswa
4. Klik menu hamburger untuk lihat QR di layar penuh

### Untuk Mahasiswa

1. Scan QR Code dengan kamera HP
2. Isi nama lengkap dan NIM
3. Pilih file yang ingin diprint
4. Klik Upload
5. Tunggu konfirmasi dari operator

## Build EXE (Optional)

Jika ingin membuat executable Windows:

```bash
cd labsend
pip install pyinstaller

# Build
pyinstaller --clean --noconsole --onedir --icon ".\app\assets\tray.ico" ".\app\main.py"
```

File EXE akan ada di folder `dist/main/`.

## Struktur Project

```
labsend/
├─ app/
│  ├─ main.py              # Entry point
│  ├─ config.py             # Konfigurasi
│  ├─ database.py          # SQLite database
│  ├─ server.py            # FastAPI server
│  ├─ tray.py              # System tray
│  ├─ qr_service.py        # QR code manager
│  ├─ upload_service.py    # Upload handler
│  ├─ file_service.py      # File operations
│  ├─ print_service.py     # Print handler
│  ├─ file_validator.py     # File validation
│  ├─ firewall_service.py  # Firewall config
│  ├─ cleanup_service.py   # Auto cleanup
│  ├─ templates/           # HTML templates
│  │  ├─ admin.html       # Dashboard
│  │  ├─ upload.html      # Upload page
│  │  ├─ qr.html          # QR display
│  │  └─ settings.html    # Settings
│  ├─ static/             # Static files
│  │  ├─ app.js
│  │  └─ style.css
│  └─ assets/             # Assets (icon, etc)
├─ data/                   # Data storage
│  └─ uploads/            # Uploaded files
└─ requirements.txt
```

## Konfigurasi

Konfigurasi tersimpan di `data/config.json`:

| Setting | Default | Deskripsi |
|---------|---------|-----------|
| `server_port` | 4711 | Port server |
| `upload_folder` | data/uploads | Folder penyimpanan |
| `max_file_size_mb` | 50 | Max size per file |
| `max_total_upload_mb` | 200 | Max total upload |
| `max_files_per_session` | 10 | Max file per upload |
| `qr_expire_seconds` | 120 | QR expired (detik) |
| `auto_delete_after_hours` | 24 | Hapus file setelah (jam) |

## Build EXE

### Persiapan

Install PyInstaller:

```bash
pip install pyinstaller
```

```bash
python -c "from PIL import Image; img=Image.open('app/static/logo.png'); img.save('app/assets/tray.ico', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])"
```

### Build

```bash
pyinstaller --noconsole --onedir --icon=app/assets/tray.ico app/main.py
pyinstaller --clean --noconsole --onedir --icon ".\app\assets\tray.ico" ".\app\main.py"
```

File EXE akan ada di folder `dist/main/`.

### Run EXE

```bash
dist\main\main.exe
```

## Keamanan

- QR token sekali pakai
- Validasi ekstensi file (blokir executable)
- Batas ukuran file
- Sanitasi nama file
- Path traversal prevention
- Dashboard hanya bisa diakses dari localhost

## Troubleshooting

### HP tidak bisa akses QR URL

1. Pastikan firewall Windows mengizinkan port 4711
2. Buka Settings > Setup Firewall di aplikasi
3. Atau buka manual: Windows Defender Firewall > Inbound Rules > New Rule

### Port sudah digunakan

Ganti port di `data/config.json`:

```json
{
  "server_port": 4712
}
```

### QR tidak muncul

Pastikan QR service berjalan. Cek logs untuk error.

## Lisensi

© 2026 azizlab.my.id. All rights reserved.

## Author

LabSend by azizlab.my.id