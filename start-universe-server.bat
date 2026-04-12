@echo off
:: ============================================================
:: Universe Server - One-Click Startup
:: Launches tray icon that manages MCP server + Cloudflare tunnel
:: Endpoint: https://tinyassets.io/mcp
:: ============================================================

set PROJECT_DIR=%~dp0
set VENV_DIR=%PROJECT_DIR%.venv

:: ---- Check Python ----
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo Python not found. Installing via winget...
    winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    if %errorlevel% neq 0 (
        echo Failed to install Python. Get it from https://www.python.org/downloads/
        pause
        exit /b 1
    )
    echo Python installed. Close this window and double-click again.
    pause
    exit /b 0
)

:: ---- Check cloudflared ----
where cloudflared >nul 2>&1
if %errorlevel% neq 0 (
    echo cloudflared not found. Installing via winget...
    winget install Cloudflare.cloudflared --accept-package-agreements --accept-source-agreements
    if %errorlevel% neq 0 (
        echo Failed to install cloudflared. See https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
        pause
        exit /b 1
    )
)

:: ---- Create venv if needed ----
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo First run - setting up environment...
    cd /d "%PROJECT_DIR%"
    python -m venv .venv
    call "%VENV_DIR%\Scripts\activate.bat"
    pip install -e . >nul 2>&1
    pip install fastmcp pystray pillow langgraph-checkpoint-sqlite >nul 2>&1
    echo Setup complete.
) else (
    call "%VENV_DIR%\Scripts\activate.bat"
)

:: ---- Launch tray app (replaces this console window) ----
cd /d "%PROJECT_DIR%"
start /b pythonw universe_tray.py
exit
