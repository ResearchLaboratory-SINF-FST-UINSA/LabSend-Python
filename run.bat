@echo off
title LabSend Print Transfer
color 0B

echo.
echo  ============================================================
echo   LabSend Print Transfer - Web Version
echo  ============================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python not found!
    echo  Please install Python from: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

echo  [✓] Python found
echo.

REM Install dependencies if needed
echo  [ ] Checking dependencies...
pip show fastapi >nul 2>&1
if errorlevel 1 (
    echo  [ ] Installing dependencies...
    pip install fastapi uvicorn jinja2 python-multipart aiofiles qrcode pillow pystray pydantic -q
    echo  [✓] Dependencies installed
) else (
    echo  [✓] Dependencies ready
)

echo.
echo  ============================================================
echo   Akses di Browser:
echo   - Dashboard: http://localhost:4711/admin
echo   - QR Page:   http://localhost:4711/qr
echo   - Settings:  http://localhost:4711/settings
echo  ============================================================
echo.
echo  Tekan Ctrl+C untuk berhenti
echo.

REM Run the application
python run_web.py

pause