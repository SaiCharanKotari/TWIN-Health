"""
main.py — TwinHealth AI Phase 1: FastAPI application entry point.
"""
from __future__ import annotations
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from config import GEMINI_API_KEY, DEFAULT_PROVIDER
from routes.detection import router as detection_router

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="TwinHealth AI — Phase 1 Detection",
    description=(
        "Academic multi-disease risk assessment system. "
        "Accepts partial patient data and returns disease risk estimates "
        "for Diabetes, Heart Disease, CKD, Liver Disease, and Stroke."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ─────────────────────────────────────────────────────────────────────
app.include_router(detection_router)

# ── Static frontend ────────────────────────────────────────────────────────────
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


@app.get("/", include_in_schema=False)
async def serve_index():
    idx = os.path.join(_FRONTEND_DIR, "index.html")
    return FileResponse(idx) if os.path.isfile(idx) else {"status": "TwinHealth API running"}


@app.get("/presentation", include_in_schema=False)
async def serve_presentation():
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "FinalYearProjectpresentain.html"))
    return FileResponse(path) if os.path.isfile(path) else {"error": "Presentation file not found"}


@app.get("/health")
async def health() -> dict:
    """Liveness probe — shows which provider is active."""
    key_ok = bool(GEMINI_API_KEY) and GEMINI_API_KEY != "your_gemini_api_key_here"
    return {
        "status":            "ok",
        "project":           "TwinHealth AI Phase 1",
        "default_provider":  DEFAULT_PROVIDER,
        "gemini_key_set":    key_ok,
        "api_docs":          "/docs",
    }
