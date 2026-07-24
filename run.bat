@echo off
title AI Career Agent - Running
echo ============================================
echo   AI Career Agent - Daily Run
echo ============================================
echo.

:: Check venv exists
if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found. Run setup.bat first.
    pause
    exit /b 1
)

:: Activate venv
call .venv\Scripts\activate.bat

:: Check .env exists
if not exist ".env" (
    echo [ERROR] .env file not found. Copy .env.example to .env and fill in your credentials.
    pause
    exit /b 1
)

echo [1/3] Running the full AI Career Agent pipeline...
echo      (Resume -^> Discovery -^> Match -^> Tailor -^> Cover Letter -^> Track -^> Analyze)
echo.
python graph_flow/graph.py

if errorlevel 1 (
    echo.
    echo [WARNING] Pipeline encountered errors. Check output above.
    echo          Launching dashboard anyway so you can review results...
    echo.
)

echo.
echo [2/3] Pipeline complete! Launching Streamlit dashboard...
echo       (Press Ctrl+C to stop the dashboard)
echo.

start "AI Career Agent - API" cmd /c "call .venv\Scripts\activate.bat && uvicorn app:app --host 127.0.0.1 --port 8000"

echo [3/3] Starting dashboard on http://localhost:8501
.venv\Scripts\streamlit.exe run dashboard.py --server.port 8501

pause
