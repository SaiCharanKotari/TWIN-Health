"""routes/detection.py — Detection API endpoints."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
import os

from schema import PatientData
from services.prediction_service import run_detection

router = APIRouter(prefix="/api/detection", tags=["detection"])


@router.post("/analyze")
async def analyze(patient: PatientData, provider: str = None) -> dict:
    """
    POST /api/detection/analyze?provider=local

    Accepts a (partial) universal patient data object.
    All fields are optional — only provided data is used.
    Returns structured risk assessments for all 5 diseases.
    """
    try:
        result = await run_detection(patient, provider_override=provider)
        return result
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "error":   "Detection service error",
                "message": "An unexpected error occurred. Please try again.",
                # Never expose stack traces or internal details to frontend
            },
        ) from exc


@router.post("/care-plan")
async def create_care_plan(payload: dict) -> dict:
    """
    POST /api/detection/care-plan

    Predicts and synthesizes personalized daily life changes (diet, exercise, vitamins,
    24-hour chronotherapy schedule, and doctor medication alignment).
    """
    try:
        from services.care_plan_service import generate_care_plan
        patient_data = payload.get("patient_data") or {}
        disease_results = payload.get("disease_results") or {}
        doctor_comments = payload.get("doctor_comments") or ""
        uploaded_prescriptions = payload.get("uploaded_prescriptions") or []

        plan = await generate_care_plan(
            patient_data=patient_data,
            disease_results=disease_results,
            doctor_comments=doctor_comments,
            uploaded_prescriptions=uploaded_prescriptions
        )
        return plan
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Care Plan Generation Error",
                "message": f"Could not synthesize care plan: {str(exc)}"
            }
        ) from exc


@router.post("/prescription/upload")
async def upload_prescription(file: UploadFile = File(...)) -> dict:
    """
    POST /api/detection/prescription/upload

    Accepts doctor prescription receipt image or document.
    Extracts prescribed medications, dosages, timings, and clinical notes.
    """
    try:
        from services.prescription_service import parse_prescription_receipt
        content = await file.read()
        parsed = await parse_prescription_receipt(
            file_bytes=content,
            filename=file.filename or "receipt.jpg",
            content_type=file.content_type or "image/jpeg"
        )
        return parsed
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Prescription Parsing Error",
                "message": f"Failed to parse prescription receipt: {str(exc)}"
            }
        ) from exc


@router.get("/template/{level}")
async def download_template(level: str) -> FileResponse:
    """
    GET /api/detection/template/basic
    GET /api/detection/template/advanced

    Download CSV templates for patient data entry.
    """
    valid = {"basic", "advanced"}
    if level not in valid:
        raise HTTPException(status_code=404, detail="Template not found. Use 'basic' or 'advanced'.")

    template_dir = os.path.join(
        os.path.dirname(__file__), "..", "..", "templates"
    )
    path = os.path.join(template_dir, f"{level}_template.csv")

    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Template file not found.")

    return FileResponse(
        path,
        media_type="text/csv",
        filename=f"twinhealth_{level}_template.csv",
    )
