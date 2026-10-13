"""
main.py — TwinHealth AI: FastAPI application entry point with multi-dashboard routing.

Serves:
- /                  Public Landing Page
- /login             Role Selection & Email Demo Login
- /input             Clinician Assessment Workspace (with mandatory Patient Email)
- /results           Persistent Prediction Results (/results?assessmentId=<id>)
- /doctor/activity   Clinician Activity Monitoring (/doctor/activity?patientEmail=...&assessmentId=...)
- /doctor            Clinician Queue & Review Workspace
- /patient           Patient Lifestyle Companion & Chronotherapy Progress Tracker
"""
from __future__ import annotations
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from config import GEMINI_API_KEY, DEFAULT_PROVIDER
from routes.detection import router as detection_router
from routes.clinical import router as clinical_router
from routes.models import router as models_router
from routes.auth import router as auth_router
from routes.activity import router as activity_router

from db.database import init_db
from db.seed import seed_demo_data
try:
    from storage.json_storage import init_storage
    from storage.seed_json import seed_demo_data_if_empty
except ImportError:
    from backend.storage.json_storage import init_storage
    from backend.storage.seed_json import seed_demo_data_if_empty


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite database and JSON file storage
    init_db()
    seed_demo_data()
    init_storage()
    seed_demo_data_if_empty()
    yield


app = FastAPI(
    title="TwinHealth AI — Clinical Risk Assessment & Lifestyle Platform",
    description=(
        "Multi-disease risk assessment system and physician care-planning platform. "
        "Evaluates Diabetes, Heart Disease, CKD, Liver Disease, and Stroke using "
        "local validated ML models, clinical workflows, and date-aware lifestyle management."
    ),
    version="2.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API Routers ────────────────────────────────────────────────────────────────
app.include_router(detection_router)
app.include_router(clinical_router)
app.include_router(models_router)
app.include_router(auth_router)
app.include_router(activity_router)

# ── Static directories ─────────────────────────────────────────────────────────
_FRONTEND_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "frontend")
)
_ASSETS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "assets")
)

if os.path.isdir(_FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=_FRONTEND_DIR), name="static")

if os.path.isdir(_ASSETS_DIR):
    app.mount("/assets", StaticFiles(directory=_ASSETS_DIR), name="assets")


# ── Frontend Browser Routes ───────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def serve_landing_page():
    path = os.path.join(_FRONTEND_DIR, "index.html")
    return FileResponse(path) if os.path.isfile(path) else {"status": "TwinHealth AI API running"}


@app.get("/login", include_in_schema=False)
async def serve_login():
    path = os.path.join(_FRONTEND_DIR, "login.html")
    return FileResponse(path) if os.path.isfile(path) else {"error": "login.html not found"}


@app.get("/input", include_in_schema=False)
async def serve_doctor_input():
    path = os.path.join(_FRONTEND_DIR, "input.html")
    return FileResponse(path) if os.path.isfile(path) else {"error": "input.html not found"}


@app.get("/results", include_in_schema=False)
async def serve_results_page():
    path = os.path.join(_FRONTEND_DIR, "results.html")
    return FileResponse(path) if os.path.isfile(path) else {"error": "results.html not found"}


@app.get("/doctor", include_in_schema=False)
async def serve_doctor_workspace():
    path = os.path.join(_FRONTEND_DIR, "doctor.html")
    return FileResponse(path) if os.path.isfile(path) else {"error": "doctor.html not found"}


@app.get("/doctor/activity", include_in_schema=False)
async def serve_doctor_activity():
    path = os.path.join(_FRONTEND_DIR, "doctor-activity.html")
    return FileResponse(path) if os.path.isfile(path) else {"error": "doctor-activity.html not found"}


@app.get("/patient", include_in_schema=False)
async def serve_patient_dashboard():
    path = os.path.join(_FRONTEND_DIR, "patient.html")
    return FileResponse(path) if os.path.isfile(path) else {"error": "patient.html not found"}


@app.get("/presentation", include_in_schema=False)
async def serve_presentation():
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "FinalYearProjectpresentain.html"))
    return FileResponse(path) if os.path.isfile(path) else {"error": "Presentation file not found"}


@app.get("/health")
async def health() -> dict:
    """Liveness & readiness probe."""
    key_ok = bool(GEMINI_API_KEY) and GEMINI_API_KEY != "your_gemini_api_key_here"
    return {
        "status":            "ok",
        "project":           "TwinHealth AI Clinical Platform",
        "default_provider":  DEFAULT_PROVIDER,
        "gemini_key_set":    key_ok,
        "database":          "sqlite_and_json_storage_synced",
        "routes": {
            "landing":          "/",
            "login":            "/login",
            "input":            "/input",
            "results":          "/results",
            "doctor":           "/doctor",
            "doctor_activity":  "/doctor/activity",
            "patient":          "/patient",
            "models_health":    "/api/models/health",
            "api_docs":         "/docs",
        }
    }


# TwinHealth AI v2.2.0 - Clinical Workflow & Medication Integration
