"""
backend/routes/activity.py — Endpoints for patient schedule completion and doctor activity monitoring.
Backed by local JSON files in data/:
- data/care_plans.json
- data/activity_completions.json
"""
from __future__ import annotations
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query, status, Request
from pydantic import BaseModel, Field

try:
    from storage import json_storage as js
except ImportError:
    from backend.storage import json_storage as js

router = APIRouter(prefix="/api/activity", tags=["activity"])


class TaskToggleRequest(BaseModel):
    patient_email: str = Field(..., description="Target patient's email")
    care_plan_id: Optional[str] = Field(None, description="Active care plan ID")
    task_id: str = Field(..., description="Unique task identifier (e.g. task_1)")
    calendar_date: Optional[str] = Field(None, description="Target calendar date YYYY-MM-DD")
    completed: bool = Field(..., description="True if marked complete, False if unchecked")
    category: Optional[str] = ""
    title: Optional[str] = ""


@router.post("/toggle")
def toggle_activity(payload: TaskToggleRequest) -> Dict[str, Any]:
    norm_email = js.normalize_email(payload.patient_email)
    if not norm_email:
        raise HTTPException(status_code=400, detail="Missing patient email.")

    plan = js.get_latest_care_plan_for_patient(norm_email)
    plan_id = payload.care_plan_id or (plan.get("id") if plan else None)
    if not plan_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No care plan found for patient {norm_email}."
        )

    task_rec = js.toggle_task_completion(
        patient_email=norm_email,
        care_plan_id=plan_id,
        task_id=payload.task_id,
        calendar_date=payload.calendar_date,
        completed=payload.completed,
        category=payload.category or "",
        title=payload.title or ""
    )

    # Return refreshed daily progress
    daily_prog = js.get_patient_daily_progress(norm_email, calendar_date=payload.calendar_date)

    return {
        "status": "success",
        "task": task_rec,
        "daily_progress": daily_prog
    }


@router.get("/patient/{patient_email}")
def get_patient_daily_activity(
    patient_email: str,
    date: Optional[str] = Query(None, description="Calendar date YYYY-MM-DD")
) -> Dict[str, Any]:
    norm_email = js.normalize_email(patient_email)
    if not norm_email:
        raise HTTPException(status_code=400, detail="Invalid patient email.")

    pat = js.get_patient_by_email(norm_email)
    prog = js.get_patient_daily_progress(norm_email, calendar_date=date)
    prog["patient_name"] = pat.get("name") if pat else norm_email.split("@")[0].title()
    prog["patient_age"] = pat.get("age") if pat else None
    prog["patient_sex"] = pat.get("sex") if pat else None
    return prog


@router.get("/patient/{patient_email}/weekly")
def get_patient_weekly_activity(
    patient_email: str,
    reference_date: Optional[str] = Query(None, description="Reference date YYYY-MM-DD")
) -> Dict[str, Any]:
    norm_email = js.normalize_email(patient_email)
    if not norm_email:
        raise HTTPException(status_code=400, detail="Invalid patient email.")

    return js.get_patient_weekly_progress(norm_email, reference_date=reference_date)


@router.get("/doctor-summary")
def get_doctor_activity_summary(
    request: Request,
    patient_email: Optional[str] = Query(None),
    assessment_id: Optional[str] = Query(None),
    date: Optional[str] = Query(None)
) -> Dict[str, Any]:
    raw_email = patient_email or request.query_params.get("patientEmail") or request.query_params.get("email")
    asm_id = assessment_id or request.query_params.get("assessmentId")
    cal_date = date or request.query_params.get("calendar_date")

    norm_email = js.normalize_email(raw_email)
    if not norm_email:
        raise HTTPException(status_code=400, detail="Missing patient email parameter.")

    pat = js.get_patient_by_email(norm_email)
    if not pat:
        # Check if user exists or create placeholder
        pat = {"id": f"pat_{norm_email}", "email": norm_email, "name": norm_email.split("@")[0].title()}

    # Resolve assessment
    asm = None
    if asm_id:
        asm = js.get_assessment_by_id(asm_id)
    if not asm:
        # Get latest assessment for patient
        asms = js.list_assessments_for_patient(norm_email)
        if asms:
            asm = asms[0]

    daily_prog = js.get_patient_daily_progress(norm_email, calendar_date=cal_date)
    weekly_prog = js.get_patient_weekly_progress(norm_email, reference_date=cal_date)

    return {
        "patient": pat,
        "assessment": asm,
        "daily": daily_prog,
        "weekly": weekly_prog
    }
