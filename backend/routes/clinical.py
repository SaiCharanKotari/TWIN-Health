"""
backend/routes/clinical.py — Endpoints for clinical intake, doctor review queue, care plans, and daily progress.
"""
from __future__ import annotations
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, Body, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from schema import PatientData
from services.prediction_service import run_detection
from services.care_plan_service import generate_care_plan
from db import repository as repo
try:
    from storage import json_storage as js
except ImportError:
    from backend.storage import json_storage as js

router = APIRouter(prefix="/api", tags=["clinical"])


# ── Pydantic Request Models ────────────────────────────────────────────────────

class AssessmentRunRequest(BaseModel):
    patient_id: Optional[str] = None
    patient_name: Optional[str] = "Anonymous Patient"
    provider: Optional[str] = "local"
    data: PatientData


class ReviewSubmitRequest(BaseModel):
    assessment_id: str
    doctor_name: Optional[str] = "Dr. Sarah Mitchell, MD"


class DoctorReviewUpdateRequest(BaseModel):
    status: str = Field(..., description="reviewed or follow_up_required or pending")
    doctor_notes: str = ""
    requested_tests: Optional[List[str]] = None
    doctor_name: Optional[str] = "Dr. Sarah Mitchell, MD"


class CarePlanDraftRequest(BaseModel):
    assessment_id: str
    provider: Optional[str] = "local"
    doctor_comments: Optional[str] = ""
    medications: Optional[List[Dict[str, Any]]] = None


class CarePlanUpdateRequest(BaseModel):
    diet: Optional[Dict[str, Any]] = None
    exercise: Optional[Dict[str, Any]] = None
    schedule: Optional[List[Dict[str, Any]]] = None
    doctor_comments: Optional[str] = None
    medications: Optional[List[Dict[str, Any]]] = None


class CarePlanApproveRequest(BaseModel):
    approved_by: Optional[str] = "Dr. Sarah Mitchell, MD"


class DailyProgressToggleRequest(BaseModel):
    patient_id: str
    care_plan_id: str
    calendar_date: str
    task_id: str
    category: str
    label: str
    completed: bool
    notes: Optional[str] = ""


# ── Assessment Intake & Running ────────────────────────────────────────────────

@router.post("/assessments/run")
async def run_and_persist_assessment(payload: AssessmentRunRequest) -> Dict[str, Any]:
    """
    Runs multi-disease detection on patient inputs and immediately persists
    both the patient profile and assessment record with a stable database ID.
    """
    try:
        detection_res = await run_detection(payload.data, provider_override=payload.provider)

        # 1. Create or resolve patient record
        patient_id = payload.patient_id or f"pat_{uuid.uuid4().hex[:8]}"
        patient = repo.create_patient(
            name=payload.patient_name or "Anonymous Patient",
            age=payload.data.age,
            sex=payload.data.sex,
            demographics={"source": "web_intake"},
            patient_id=patient_id
        )

        # Calculate completeness
        completeness = 0.0
        results = detection_res.get("results", {})
        if results:
            completeness = round(sum(r.get("input_summary", {}).get("data_completeness", 0.0) for r in results.values()) / len(results), 2)

        # 2. Persist assessment
        asm = repo.create_assessment(
            patient_id=patient["id"],
            inputs=payload.data.model_dump(),
            normalized_inputs=detection_res.get("patient_summary", {}),
            disease_results=results,
            status="draft",
            provider=payload.provider or "local",
            data_completeness=completeness
        )

        return {
            "assessment_id": asm["id"],
            "patient_id": patient["id"],
            "patient_name": patient["name"],
            "detection": detection_res,
            "status": asm["status"],
            "created_at": asm["created_at"],
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"error": "Assessment Error", "message": f"Failed to execute assessment: {str(exc)}"}
        ) from exc


def normalize_assessment_record(asm: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalizes an assessment record from JSON storage or SQLite into the canonical
    TwinHealth API response contract:
    - patient_summary: Patient demographics and biomarker inputs
    - results: 5-disease model prediction results
    - summary: Assessment and engine metadata
    - disclaimer: Clinical disclaimer
    Preserves all database and storage metadata (id, patient_email, care_plan_id, etc.).
    """
    if not isinstance(asm, dict):
        return {}

    record = dict(asm)

    # 1. Normalize patient_summary from normalized_inputs / inputs
    patient_summary = (
        record.get("patient_summary")
        or record.get("normalized_inputs")
        or record.get("inputs")
    )
    if not isinstance(patient_summary, dict):
        patient_summary = {}
    else:
        patient_summary = dict(patient_summary)

    # Ensure patient metadata (name, age, sex) is aligned if available
    if "patient_age" in record and record["patient_age"] is not None and "age" not in patient_summary:
        patient_summary["age"] = record["patient_age"]
    if "patient_sex" in record and record["patient_sex"] is not None and "sex" not in patient_summary:
        patient_summary["sex"] = record["patient_sex"]

    # 2. Normalize results from disease_results / results
    results = record.get("results") or record.get("disease_results")
    if not isinstance(results, dict):
        results = {}
    else:
        results = dict(results)

    # 3. Normalize summary metadata
    summary = record.get("summary")
    if not isinstance(summary, dict):
        models_run = len(results)
        models_success = sum(1 for r in results.values() if isinstance(r, dict) and r.get("status") == "success")
        models_insufficient = sum(1 for r in results.values() if isinstance(r, dict) and r.get("status") == "insufficient_data")
        models_preliminary = sum(1 for r in results.values() if isinstance(r, dict) and r.get("status") == "preliminary")
        models_unavailable = sum(1 for r in results.values() if isinstance(r, dict) and r.get("status") == "model_unavailable")
        summary = {
            "assessment_id": record.get("id"),
            "models_run": models_run,
            "models_success": models_success,
            "models_insufficient": models_insufficient,
            "models_preliminary": models_preliminary,
            "models_unavailable": models_unavailable,
            "data_completeness": record.get("data_completeness", 0.0),
            "timestamp": record.get("created_at") or record.get("timestamp") or datetime.now(timezone.utc).isoformat(),
            "provider": record.get("provider", "local"),
        }
    else:
        summary = dict(summary)

    # 4. Disclaimer
    disclaimer = record.get("disclaimer") or (
        "This system is an academic AI-based risk prediction tool and is NOT a substitute "
        "for professional medical diagnosis or treatment."
    )

    record["patient_summary"] = patient_summary
    record["results"] = results
    record["disease_results"] = results
    record["summary"] = summary
    record["disclaimer"] = disclaimer
    record["medication_record"] = record.get("medication_record")
    return record


@router.get("/assessments/{assessment_id}")
def get_assessment(assessment_id: str) -> Dict[str, Any]:
    # 1. Check local JSON storage first
    asm_json = js.get_assessment_by_id(assessment_id)
    if asm_json:
        pat = js.get_patient_by_email(asm_json.get("patient_email") or "")
        if pat:
            asm_json["patient_name"] = pat.get("name")
            asm_json["patient_age"] = pat.get("age")
            asm_json["patient_sex"] = pat.get("sex")
        plan = js.get_latest_care_plan_for_patient(asm_json.get("patient_email") or "")
        if plan:
            asm_json["care_plan"] = plan
            asm_json["care_plan_id"] = plan.get("id")
        return normalize_assessment_record(asm_json)

    # 2. Fall back to SQLite repository
    asm = repo.get_assessment_by_id(assessment_id)
    if not asm:
        raise HTTPException(status_code=404, detail="Assessment record not found")
    # Attach linked review if present
    review = repo.get_review_by_assessment_id(assessment_id)
    asm["review"] = review
    return normalize_assessment_record(asm)


@router.get("/patients")
def list_patients(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    return repo.list_patients(limit=limit, offset=offset)


@router.get("/patients/{patient_id}")
def get_patient(patient_id: str) -> Dict[str, Any]:
    pat = repo.get_patient_by_id(patient_id)
    if not pat:
        raise HTTPException(status_code=404, detail="Patient not found")
    # Attach recent assessments
    pat["assessments"] = repo.list_assessments_for_patient(patient_id)
    return pat


# ── Clinical Review Workflow ───────────────────────────────────────────────────

@router.post("/reviews/submit")
def submit_for_doctor_review(payload: ReviewSubmitRequest) -> Dict[str, Any]:
    """
    Handoff from patient intake to doctor review:
    Validates assessment existence and transitions status to 'pending_review'.
    """
    asm = repo.get_assessment_by_id(payload.assessment_id)
    if not asm:
        raise HTTPException(status_code=404, detail="Assessment not found")

    rev = repo.create_or_update_review(
        assessment_id=payload.assessment_id,
        doctor_name=payload.doctor_name or "Dr. Sarah Mitchell, MD",
        status="pending",
        doctor_notes="",
        requested_tests=[]
    )

    return {
        "status": "pending_review",
        "review_id": rev["id"],
        "assessment_id": payload.assessment_id,
        "patient_id": asm["patient_id"],
        "message": "Assessment successfully submitted for clinician review."
    }


@router.get("/reviews/queue")
def get_doctor_review_queue(
    status: Optional[str] = Query(None, description="all, pending, reviewed, follow_up_required"),
    search: Optional[str] = Query(None),
    limit: int = 50,
    offset: int = 0
) -> Dict[str, Any]:
    cases = repo.list_doctor_queue(status_filter=status, search=search, limit=limit, offset=offset)
    kpis = repo.get_dashboard_kpis()
    return {
        "cases": cases,
        "kpis": kpis,
        "total": len(cases),
    }


@router.get("/reviews/stats")
def get_reviews_stats() -> Dict[str, Any]:
    return repo.get_dashboard_kpis()


@router.get("/reviews/{assessment_id}")
def get_assessment_review(assessment_id: str) -> Dict[str, Any]:
    rev = repo.get_review_by_assessment_id(assessment_id)
    if not rev:
        return {"assessment_id": assessment_id, "status": "pending", "doctor_notes": "", "requested_tests": []}
    return rev


@router.post("/reviews/{assessment_id}/update")
def update_clinical_review(assessment_id: str, payload: DoctorReviewUpdateRequest) -> Dict[str, Any]:
    asm = repo.get_assessment_by_id(assessment_id)
    if not asm:
        raise HTTPException(status_code=404, detail="Assessment not found")

    updated = repo.create_or_update_review(
        assessment_id=assessment_id,
        doctor_name=payload.doctor_name or "Dr. Sarah Mitchell, MD",
        status=payload.status,
        doctor_notes=payload.doctor_notes,
        requested_tests=payload.requested_tests or []
    )
    return updated


# ── Care Plan Management ───────────────────────────────────────────────────────

@router.post("/care-plans/draft")
async def draft_care_plan(payload: CarePlanDraftRequest) -> Dict[str, Any]:
    """
    Generates a draft care plan from the saved assessment using deterministic CDS,
    saves it to the database with status='draft', and links to the patient.
    """
    asm = repo.get_assessment_by_id(payload.assessment_id)
    if not asm:
        raise HTTPException(status_code=404, detail="Assessment not found")

    # Generate plan via CDS
    plan_dict = await generate_care_plan(
        patient_data=asm.get("inputs", {}),
        disease_results=asm.get("disease_results", {}),
        doctor_comments=payload.doctor_comments or "",
        uploaded_prescriptions=payload.medications or [],
        provider=payload.provider or "local"
    )

    diet = plan_dict.get("diet", {})
    exercise = plan_dict.get("exercise", {})
    schedule = plan_dict.get("chronotherapy_schedule", [])

    # Format schedule to consistent format if needed
    cleaned_schedule = []
    for s in schedule:
        cleaned_schedule.append({
            "time": s.get("time", ""),
            "period": s.get("period", "Morning"),
            "category": s.get("category", "lifestyle"),
            "task": s.get("task") or s.get("action") or s.get("title", ""),
        })

    # Persist draft care plan
    saved_plan = repo.create_or_update_care_plan(
        patient_id=asm["patient_id"],
        assessment_id=asm["id"],
        diet=diet,
        exercise=exercise,
        schedule=cleaned_schedule,
        status="draft",
        medications=payload.medications or [],
        lifestyle=plan_dict.get("active_risks", {}),
        doctor_comments=payload.doctor_comments or ""
    )

    return saved_plan


@router.put("/care-plans/{care_plan_id}")
def update_care_plan(care_plan_id: str, payload: CarePlanUpdateRequest) -> Dict[str, Any]:
    current = repo.get_care_plan_by_id(care_plan_id)
    if not current:
        raise HTTPException(status_code=404, detail="Care plan not found")

    diet = payload.diet if payload.diet is not None else current.get("diet", {})
    exercise = payload.exercise if payload.exercise is not None else current.get("exercise", {})
    schedule = payload.schedule if payload.schedule is not None else current.get("schedule", [])
    meds = payload.medications if payload.medications is not None else current.get("medications", [])
    comments = payload.doctor_comments if payload.doctor_comments is not None else current.get("doctor_comments", "")

    updated = repo.create_or_update_care_plan(
        patient_id=current["patient_id"],
        assessment_id=current.get("assessment_id"),
        diet=diet,
        exercise=exercise,
        schedule=schedule,
        status=current.get("status", "draft"),
        medications=meds,
        lifestyle=current.get("lifestyle", {}),
        doctor_comments=comments,
        plan_id=care_plan_id
    )
    return updated


@router.post("/care-plans/{care_plan_id}/approve")
def approve_and_publish_care_plan(care_plan_id: str, payload: CarePlanApproveRequest) -> Dict[str, Any]:
    """
    Approves a drafted care plan and publishes it as the active plan for the patient dashboard.
    """
    try:
        approved = repo.approve_care_plan(care_plan_id, approved_by=payload.approved_by or "Dr. Sarah Mitchell, MD")
        return {
            "status": "approved",
            "message": "Care plan approved and published to patient dashboard.",
            "care_plan": approved
        }
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve)) from ve


@router.get("/care-plans/patient/{patient_id}/current")
def get_current_care_plan(patient_id: str) -> Dict[str, Any]:
    """Retrieves the currently approved care plan for the patient dashboard."""
    plan = repo.get_latest_approved_care_plan(patient_id)
    if not plan:
        raise HTTPException(status_code=404, detail="No care plan found for patient")
    return plan


@router.get("/care-plans/patient/{patient_id}/history")
def get_care_plan_history(patient_id: str) -> List[Dict[str, Any]]:
    return repo.list_care_plans_for_patient(patient_id)


# ── Daily Progress & Tracking ──────────────────────────────────────────────────

@router.get("/progress/{patient_id}")
def get_daily_progress(
    patient_id: str,
    date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format")
) -> Dict[str, Any]:
    target_date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    current_plan = repo.get_latest_approved_care_plan(patient_id)

    logged_tasks = repo.get_daily_progress_for_date(patient_id, target_date)
    logged_map = {t["task_id"]: t for t in logged_tasks}

    # If an approved plan exists, combine its schedule with completion status
    schedule_items = []
    if current_plan:
        schedule = current_plan.get("schedule", [])
        for i, item in enumerate(schedule):
            tid = f"task_{i+1}"
            log_entry = logged_map.get(tid)
            is_comp = bool(log_entry["completed"]) if log_entry else False
            schedule_items.append({
                "task_id": tid,
                "time": item.get("time", ""),
                "period": item.get("period", "Morning"),
                "category": item.get("category", "lifestyle"),
                "label": item.get("task", ""),
                "completed": is_comp,
                "completed_at": log_entry.get("completed_at") if log_entry else None,
            })

    total = len(schedule_items)
    completed_count = sum(1 for s in schedule_items if s["completed"])
    percentage = int(round((completed_count / total) * 100)) if total > 0 else 0

    return {
        "patient_id": patient_id,
        "calendar_date": target_date,
        "care_plan_id": current_plan.get("id") if current_plan else None,
        "care_plan_status": current_plan.get("status") if current_plan else "no_plan",
        "approved_by": current_plan.get("approved_by") if current_plan else None,
        "approved_at": current_plan.get("approved_at") if current_plan else None,
        "doctor_comments": current_plan.get("doctor_comments") if current_plan else "",
        "total_tasks": total,
        "completed_tasks": completed_count,
        "completion_percentage": percentage,
        "tasks": schedule_items,
        "diet": current_plan.get("diet") if current_plan else {},
        "exercise": current_plan.get("exercise") if current_plan else {},
    }


@router.post("/progress/toggle")
def toggle_progress_task(payload: DailyProgressToggleRequest) -> Dict[str, Any]:
    result = repo.toggle_daily_task_completion(
        patient_id=payload.patient_id,
        care_plan_id=payload.care_plan_id,
        calendar_date=payload.calendar_date,
        task_id=payload.task_id,
        category=payload.category,
        label=payload.label,
        completed=payload.completed,
        notes=payload.notes or ""
    )
    return {"status": "success", "task": result}


@router.get("/progress/{patient_id}/weekly")
def get_weekly_adherence(patient_id: str) -> Dict[str, Any]:
    return repo.get_weekly_progress_summary(patient_id)


@router.get("/dashboard/kpis")
def get_kpis() -> Dict[str, int]:
    return repo.get_dashboard_kpis()


# ── Medication / Prescription Upload & Download Endpoints ────────────────────

@router.post("/assessments/{assessment_id}/medications/upload")
async def upload_assessment_medication(
    assessment_id: str,
    file: UploadFile = File(...),
    notes: Optional[str] = Form(None),
    patient_email: Optional[str] = Form(None)
) -> Dict[str, Any]:
    """Uploads an optional prescription/medication file, saves it, and links to assessment and patient."""
    # Ensure medication directory exists
    js.MEDICATIONS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Look up assessment
    asm = js.get_assessment_by_id(assessment_id)
    if not asm:
        asm = repo.get_assessment_by_id(assessment_id)
        if not asm:
            raise HTTPException(status_code=404, detail="Assessment not found")

    target_email = js.normalize_email(patient_email or asm.get("patient_email"))
    file_id = f"med_{uuid.uuid4().hex[:10]}"
    safe_name = os.path.basename(file.filename or "prescription_document.pdf").replace(" ", "_")
    saved_filename = f"{file_id}_{safe_name}"
    saved_path = js.MEDICATIONS_DIR / saved_filename

    content = await file.read()
    with open(saved_path, "wb") as f:
        f.write(content)

    parsed_meds = []
    try:
        from services.prescription_service import parse_prescription_receipt
        parsed = await parse_prescription_receipt(
            file_bytes=content,
            filename=file.filename or "receipt.jpg",
            content_type=file.content_type or "application/octet-stream"
        )
        if parsed and isinstance(parsed, dict):
            parsed_meds = parsed.get("medications") or []
    except Exception:
        parsed_meds = []

    record = js.save_medication_record(
        file_id=file_id,
        original_filename=file.filename or safe_name,
        file_path=str(saved_path),
        patient_email=target_email,
        assessment_id=assessment_id,
        notes=notes or "",
        medications=parsed_meds
    )

    return {
        "status": "success",
        "file_id": file_id,
        "filename": file.filename or safe_name,
        "download_url": f"/api/medications/{file_id}/download",
        "uploaded_at": record.get("uploaded_at"),
        "notes": notes or "",
        "medications": parsed_meds,
        "medication_record": record,
    }


@router.get("/medications/{file_id}/download")
def download_medication_file(file_id: str):
    """Streams the uploaded medication/prescription file for downloading."""
    record = js.get_medication_record(file_id)
    if not record:
        raise HTTPException(status_code=404, detail="Medication file record not found")

    file_path = record.get("file_path")
    if not file_path or not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File on disk not found")

    filename = record.get("filename") or os.path.basename(file_path)
    return FileResponse(file_path, filename=filename)


@router.get("/patients/{patient_email}/medications")
def get_patient_medication_files(patient_email: str) -> Dict[str, Any]:
    """Retrieves the latest uploaded medication file for a patient."""
    norm_email = js.normalize_email(patient_email)
    record = js.get_patient_medications(norm_email)
    if not record:
        return {"patient_email": norm_email, "has_medication": False, "medication": None, "medications": []}

    return {
        "patient_email": norm_email,
        "has_medication": True,
        "medication": record,
        "medications": [record]
    }

