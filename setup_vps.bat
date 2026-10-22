@echo off
cd /d "%~dp0"
title Journa NextGen - 1-Click VPS Installer
echo ========================================================
echo        Journa NextGen - 1-Click Setup for Windows VPS
echo ========================================================
echo.
echo Installing Python dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo.
echo ========================================================
echo  [✓] Dependencies installed successfully!
echo  To start Journa NextGen on VPS, run: start_dingjourney.bat
echo ========================================================
echo.
pause
