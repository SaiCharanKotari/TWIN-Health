@echo off
title MediRisk — Clinical Assessment Server

:: Check .env exists
if not exist ".env" (
    echo.
    echo  [!] .env file not found.
    echo  [!] Copy .env.example to .env and add your Gemini API key.
    echo.
    echo      copy .env.example .env
    echo      Then edit .env and set GEMINI_API_KEY=your_key_here
    echo.
    pause
    exit /b 1
)

:: Install dependencies (only if needed)
echo [*] Checking Python dependencies...
pip install -r requirements.txt --quiet

echo.
echo [*] Starting MediRisk server...
echo [*] Open your browser at: http://localhost:8000
echo [*] Press Ctrl+C to stop.
echo.

cd backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
