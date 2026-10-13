@echo off
title TwinHealth AI — Digital Twin Clinical Platform

echo ========================================================
echo    TwinHealth AI — Multi-Disease Clinical Platform
echo ========================================================
echo.

:: Auto-create .env if not found
if not exist ".env" (
    echo [*] Creating default local .env file...
    echo DEFAULT_PROVIDER=local > .env
    echo ENVIRONMENT=development >> .env
    echo HOST=0.0.0.0 >> .env
    echo PORT=8000 >> .env
)

:: Install dependencies
echo [*] Checking Python dependencies...
pip install -r requirements.txt --quiet

echo.
echo [*] Starting TwinHealth AI server with Local ML Models...
echo.
echo    [+] Patient Intake Portal:   http://localhost:8000
echo    [+] Physician Workspace:      http://localhost:8000/doctor
echo    [+] Patient Care Tracker:     http://localhost:8000/patient
echo    [+] API Health Check:         http://localhost:8000/api/models/health
echo.
echo [*] Press Ctrl+C to terminate.
echo.

cd backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
