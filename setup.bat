@echo off
title AI Career Agent - Setup
echo ============================================
echo   AI Career Agent - One-Time Setup
echo ============================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo         Install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

:: Create virtual environment
if not exist ".venv" (
    echo [1/4] Creating virtual environment...
    python -m venv .venv
) else (
    echo [1/4] Virtual environment already exists, skipping.
)

:: Activate venv
echo [2/4] Activating virtual environment...
call .venv\Scripts\activate.bat

:: Install dependencies
echo [3/4] Installing Python dependencies...
pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt

:: Install Playwright browsers
echo [4/4] Installing Playwright browsers (for web scraping)...
playwright install chromium

echo.
echo ============================================
echo   Setup Complete!
echo ============================================
echo.
echo   Next steps:
echo   1. Edit .env with your credentials (Groq API key is already set)
echo   2. Replace resumes/master_resume.pdf with your real resume
echo   3. Double-click run.bat to launch the pipeline
echo.
pause
