"""routes/detection.py — Detection API endpoints (with database persistence)."""
from __future__ import annotations
import os
import uuid
from fastapi import APIRouter, HTTPException, UploadFile, File, Request
from fastapi.responses import FileResponse

from schema import PatientData
from services.prediction_service import run_detection
from db import repository as repo
try:
    from storage import json_storage as js
except ImportError:
    from backend.storage import json_storage as js

router = APIRouter(prefix="/api/detection", tags=["detection"])


@router.post("/analyze")
async def analyze(request: Request, provider: str = None) -> dict:
    """
    POST /api/detection/analyze?provider=local

    Accepts universal patient data with mandatory/optional patient_email.
    Runs local ML detection, persists patient, assessment, and structured care plan
    to data/*.json and SQLite, and returns assessment_id and patient_email for navigation.
    """
    try:
        body = await request.json()
        if not isinstance(body, dict):
            body = {}

        # 1. Extract patient_email and doctor_email
        patient_email = js.normalize_email(
            body.get("patient_email") or body.get("email") or request.query_params.get("patient_email")
        )
        if not patient_email:
            patient_email = f"patient_{uuid.uuid4().hex[:6]}@demo.local"

        doctor_email = js.normalize_email(
            body.get("doctor_email") or request.query_params.get("doctor_email") or "doctor@twinhealth.demo"
        )

        patient_name = body.get("patient_name") or body.get("name") or patient_email.split("@")[0].title()
        eff_provider = provider or body.get("provider") or "local"

        # 2. Extract clinical patient data
        if "data" in body and isinstance(body["data"], dict):
            p_dict = body["data"]
        elif "patient" in body and isinstance(body["patient"], dict):
            p_dict = body["patient"]
        else:
            # Exclude non-clinical metadata
            excluded = {"patient_email", "doctor_email", "patient_name", "provider", "email", "name"}
            p_dict = {k: v for k, v in body.items() if k not in excluded}

        patient = PatientData(**p_dict)
        result = await run_detection(patient, provider_override=eff_provider)

        # 3. Calculate data completeness
        completeness = 0.0
        results = result.get("results", {})
        if results:
            completeness = round(
                sum(r.get("input_summary", {}).get("data_completeness", 0.0) for r in results.values()) / len(results), 2
            )

        # 4. Persist to local JSON storage (data/*.json)
        pat = js.upsert_patient(
            email=patient_email,
            name=patient_name,
            age=patient.age,
            sex=patient.sex,
            demographics={"source": "detection_analyze"}
        )

        asm = js.create_assessment(
            patient_id=pat["id"],
            patient_email=patient_email,
            doctor_email=doctor_email,
            inputs=patient.model_dump(),
            normalized_inputs=result.get("patient_summary", {}),
            disease_results=results,
            status="completed",
            provider=eff_provider,
            data_completeness=completeness
        )

        # 5. Synthesize & store personalized care plan with structured tasks
        try:
            from services.care_plan_service import generate_care_plan
            plan_dict = await generate_care_plan(
                patient_data=patient.model_dump(),
                disease_results=results,
                doctor_comments="Routine cardiometabolic & lifestyle protocol.",
                provider="local"
            )
            care_plan = js.create_or_update_care_plan(
                patient_email=patient_email,
                patient_id=pat["id"],
                assessment_id=asm["id"],
                plan_dict=plan_dict,
                doctor_comments="Approved comprehensive care plan.",
                status="approved",
                doctor_name="Attending Physician, MD"
            )
            result["care_plan_id"] = care_plan["id"]
        except Exception as plan_exc:
            import traceback
            traceback.print_exc()
            care_plan = None

        # 6. Also persist to SQLite repository for backwards compatibility
        try:
            repo.create_patient(
                name=patient_name,
                age=patient.age,
                sex=patient.sex,
                demographics={"source": "detection_analyze"},
                patient_id=pat["id"]
            )
            repo.create_assessment(
                patient_id=pat["id"],
                inputs=patient.model_dump(),
                normalized_inputs=result.get("patient_summary", {}),
                disease_results=results,
                status="draft",
                provider=eff_provider,
                data_completeness=completeness,
                assessment_id=asm["id"]
            )
        except Exception:
            pass

        result["assessment_id"] = asm["id"]
        result["patient_id"] = pat["id"]
        result["patient_email"] = patient_email
        result["doctor_email"] = doctor_email
        return result
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "error":   "Detection service error",
                "message": f"Detection processing error: {str(exc)}",
            },
        ) from exc


@router.post("/care-plan")
async def create_care_plan(payload: dict) -> dict:
    """
    POST /api/detection/care-plan

    Predicts and synthesizes personalized daily life changes (diet, exercise,
    24-hour chronotherapy schedule, and doctor medication alignment).
    """
    try:
        from services.care_plan_service import generate_care_plan
        patient_data = payload.get("patient_data") or {}
        disease_results = payload.get("disease_results") or {}
        doctor_comments = payload.get("doctor_comments") or ""
        uploaded_prescriptions = payload.get("uploaded_prescriptions") or []
        provider = payload.get("provider") or "local"

        plan = await generate_care_plan(
            patient_data=patient_data,
            disease_results=disease_results,
            doctor_comments=doctor_comments,
            uploaded_prescriptions=uploaded_prescriptions,
            provider=provider
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
    Extracts prescribed medications with strict safety verification protocol.
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
