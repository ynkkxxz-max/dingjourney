@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
title Journa NextGen - Trading Calendar Dashboard & MT5 Sync

python launcher.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ========================================================
    echo Error: Failed to start Python.
    echo Please make sure Python is installed and added to PATH.
    echo ========================================================
    pause
)
