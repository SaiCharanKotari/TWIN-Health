"""
backend/storage/json_storage.py — Thread-safe, atomic, local JSON persistence engine.

Stores and manages:
- data/users.json
- data/patients.json
- data/assessments.json
- data/care_plans.json
- data/activity_completions.json

Features:
- Path resolution independent of current working directory (uses project root).
- Atomic writes via temporary files and os.replace().
- Process-wide thread serialization with threading.Lock().
- Case/whitespace normalization for all email identities.
- Idempotent activity task completion recording.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("twinhealth.storage")

# Root data directory located at <project_root>/data
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"

_WRITE_LOCK = threading.Lock()

# Filenames
USERS_FILE = "users.json"
PATIENTS_FILE = "patients.json"
ASSESSMENTS_FILE = "assessments.json"
CARE_PLANS_FILE = "care_plans.json"
COMPLETIONS_FILE = "activity_completions.json"
MEDICATIONS_FILE = "medications.json"
MEDICATIONS_DIR = DATA_DIR / "medications"


def normalize_email(email: Optional[str]) -> str:
    """Trims whitespace and lowercases email address."""
    if not email:
        return ""
    return str(email).strip().lower()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today_date_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def init_storage() -> None:
    """Ensure data/ directory and JSON storage files exist with valid initial structure."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MEDICATIONS_DIR.mkdir(parents=True, exist_ok=True)
    for filename in [USERS_FILE, PATIENTS_FILE, ASSESSMENTS_FILE, CARE_PLANS_FILE, COMPLETIONS_FILE, MEDICATIONS_FILE]:
        file_path = DATA_DIR / filename
        if not file_path.exists():
            _write_json_direct(filename, [])


def _read_json_direct(filename: str) -> List[Dict[str, Any]]:
    """Reads JSON data from file safely. Returns empty list if missing or corrupted."""
    file_path = DATA_DIR / filename
    if not file_path.exists():
        return []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return []
            data = json.loads(content)
            return data if isinstance(data, list) else []
    except Exception as exc:
        logger.error(f"Error reading JSON from {file_path}: {exc}")
        return []


def _write_json_direct(filename: str, data: List[Dict[str, Any]]) -> None:
    """Atomically writes JSON data to file using a temporary file and os.replace."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    target_path = DATA_DIR / filename

    with tempfile.NamedTemporaryFile("w", dir=str(DATA_DIR), delete=False, encoding="utf-8") as tf:
        json.dump(data, tf, indent=2, ensure_ascii=False)
        tf.flush()
        os.fsync(tf.fileno())
        temp_path = Path(tf.name)

    os.replace(temp_path, target_path)


# ── User Identity Storage (data/users.json) ───────────────────────────────────

def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    norm_email = normalize_email(email)
    if not norm_email:
        return None
    with _WRITE_LOCK:
        users = _read_json_direct(USERS_FILE)
        for u in users:
            if normalize_email(u.get("email")) == norm_email:
                return dict(u)
    return None


def upsert_user(email: str, role: str, display_name: str = "") -> Dict[str, Any]:
    norm_email = normalize_email(email)
    role = (role or "patient").lower().strip()
    now = _utc_now_iso()

    with _WRITE_LOCK:
        users = _read_json_direct(USERS_FILE)
        found = None
        for u in users:
            if normalize_email(u.get("email")) == norm_email:
                found = u
                break

        if found:
            found["last_login"] = now
            found["role"] = role
            if display_name:
                found["display_name"] = display_name
            found["updated_at"] = now
            res = dict(found)
        else:
            default_name = display_name or norm_email.split("@")[0].replace(".", " ").title()
            res = {
                "email": norm_email,
                "role": role,
                "display_name": default_name,
                "first_seen": now,
                "last_login": now,
                "created_at": now,
                "updated_at": now
            }
            users.append(res)

        _write_json_direct(USERS_FILE, users)
        return res


def list_users() -> List[Dict[str, Any]]:
    with _WRITE_LOCK:
        return _read_json_direct(USERS_FILE)


# ── Patient Storage (data/patients.json) ───────────────────────────────────────

def get_patient_by_email(email: str) -> Optional[Dict[str, Any]]:
    norm_email = normalize_email(email)
    if not norm_email:
        return None
    with _WRITE_LOCK:
        patients = _read_json_direct(PATIENTS_FILE)
        for p in patients:
            if normalize_email(p.get("email")) == norm_email:
                return dict(p)
    return None


def get_patient_by_id(patient_id: str) -> Optional[Dict[str, Any]]:
    if not patient_id:
        return None
    with _WRITE_LOCK:
        patients = _read_json_direct(PATIENTS_FILE)
        for p in patients:
            if p.get("id") == patient_id:
                return dict(p)
    return None


def upsert_patient(
    email: str,
    name: Optional[str] = None,
    age: Optional[int] = None,
    sex: Optional[str] = None,
    demographics: Optional[Dict[str, Any]] = None,
    patient_id: Optional[str] = None
) -> Dict[str, Any]:
    norm_email = normalize_email(email)
    now = _utc_now_iso()

    with _WRITE_LOCK:
        patients = _read_json_direct(PATIENTS_FILE)
        found = None
        for p in patients:
            if normalize_email(p.get("email")) == norm_email or (patient_id and p.get("id") == patient_id):
                found = p
                break

        if found:
            if name:
                found["name"] = name
            if age is not None:
                found["age"] = age
            if sex:
                found["sex"] = sex
            if demographics:
                demo = found.get("demographics") or {}
                demo.update(demographics)
                found["demographics"] = demo
            found["updated_at"] = now
            res = dict(found)
        else:
            pid = patient_id or f"pat_{uuid.uuid4().hex[:10]}"
            calc_name = name or (norm_email.split("@")[0].replace(".", " ").title() if norm_email else "Patient")
            res = {
                "id": pid,
                "email": norm_email,
                "name": calc_name,
                "age": age,
                "sex": sex,
                "demographics": demographics or {},
                "created_at": now,
                "updated_at": now
            }
            patients.append(res)

        _write_json_direct(PATIENTS_FILE, patients)
        return res


def list_patients() -> List[Dict[str, Any]]:
    with _WRITE_LOCK:
        return _read_json_direct(PATIENTS_FILE)


# ── Assessment Storage (data/assessments.json) ──────────────────────────────────

def create_assessment(
    patient_id: str,
    patient_email: str,
    inputs: Dict[str, Any],
    disease_results: Dict[str, Any],
    doctor_email: Optional[str] = None,
    status: str = "completed",
    provider: str = "local",
    data_completeness: float = 0.0,
    warnings: Optional[List[str]] = None,
    normalized_inputs: Optional[Dict[str, Any]] = None,
    assessment_id: Optional[str] = None
) -> Dict[str, Any]:
    aid = assessment_id or f"asm_{uuid.uuid4().hex[:10]}"
    norm_patient_email = normalize_email(patient_email)
    norm_doctor_email = normalize_email(doctor_email)
    now = _utc_now_iso()

    rec = {
        "id": aid,
        "patient_id": patient_id,
        "patient_email": norm_patient_email,
        "doctor_email": norm_doctor_email,
        "inputs": inputs,
        "normalized_inputs": normalized_inputs or inputs,
        "disease_results": disease_results,
        "status": status,
        "provider": provider,
        "data_completeness": data_completeness,
        "warnings": warnings or [],
        "care_plan_id": None,
        "created_at": now,
        "updated_at": now
    }

    with _WRITE_LOCK:
        assessments = _read_json_direct(ASSESSMENTS_FILE)
        # Update if exists with same id, else append
        idx = next((i for i, a in enumerate(assessments) if a.get("id") == aid), None)
        if idx is not None:
            assessments[idx] = rec
        else:
            assessments.insert(0, rec)
        _write_json_direct(ASSESSMENTS_FILE, assessments)

    return rec


def get_assessment_by_id(assessment_id: str) -> Optional[Dict[str, Any]]:
    if not assessment_id:
        return None
    with _WRITE_LOCK:
        assessments = _read_json_direct(ASSESSMENTS_FILE)
        for a in assessments:
            if a.get("id") == assessment_id:
                return dict(a)
    return None


def list_assessments_for_patient(patient_email: str) -> List[Dict[str, Any]]:
    norm_email = normalize_email(patient_email)
    if not norm_email:
        return []
    with _WRITE_LOCK:
        assessments = _read_json_direct(ASSESSMENTS_FILE)
        return [dict(a) for a in assessments if normalize_email(a.get("patient_email")) == norm_email]


def list_all_assessments(limit: int = 50) -> List[Dict[str, Any]]:
    with _WRITE_LOCK:
        assessments = _read_json_direct(ASSESSMENTS_FILE)
        return assessments[:limit]


# ── Care Plan Storage (data/care_plans.json) ───────────────────────────────────

def create_or_update_care_plan(
    patient_email: str,
    patient_id: str,
    assessment_id: Optional[str],
    plan_dict: Dict[str, Any],
    doctor_comments: str = "",
    status: str = "approved",
    doctor_name: Optional[str] = "Attending Physician, MD",
    plan_id: Optional[str] = None
) -> Dict[str, Any]:
    norm_email = normalize_email(patient_email)
    now = _utc_now_iso()
    pid = plan_id or f"cpl_{uuid.uuid4().hex[:10]}"

    # Structure tasks with stable task_ids if not already structured
    chronotherapy = plan_dict.get("chronotherapy_schedule") or []
    structured_tasks = []
    task_idx = 1
    for item in chronotherapy:
        tid = item.get("task_id") or f"task_{task_idx}"
        structured_tasks.append({
            "task_id": tid,
            "care_plan_id": pid,
            "patient_email": norm_email,
            "time": item.get("time") or "08:00 AM",
            "period": item.get("period") or "Morning",
            "category": item.get("category") or "wellness",
            "title": item.get("title") or item.get("action", f"Task {task_idx}"),
            "description": item.get("action") or item.get("title", ""),
            "icon": item.get("icon") or "✓",
            "cadence": "daily",
            "applicable_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        })
        task_idx += 1

    # Weekly exercise goal as a weekly structured task
    exercise_data = plan_dict.get("exercise") or {}
    if exercise_data.get("weekly_goal_mins"):
        structured_tasks.append({
            "task_id": "weekly_exercise_goal",
            "care_plan_id": pid,
            "patient_email": norm_email,
            "time": "Weekly",
            "period": "Weekly Goal",
            "category": "exercise",
            "title": f"Complete {exercise_data.get('weekly_goal_mins')} mins of moderate Zone-2 cardio",
            "description": exercise_data.get("regimen_name", "Cardio protocol"),
            "icon": "🏃",
            "cadence": "weekly",
            "applicable_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        })

    rec = {
        "id": pid,
        "patient_id": patient_id,
        "patient_email": norm_email,
        "assessment_id": assessment_id,
        "version": 1,
        "status": status,
        "title": plan_dict.get("title") or "Personalized Cardiometabolic & Lifestyle Care Plan",
        "summary": plan_dict.get("summary") or "Daily lifestyle intervention protocol.",
        "active_risks": plan_dict.get("active_risks") or {},
        "diet": plan_dict.get("diet") or {},
        "exercise": exercise_data,
        "vitamins_and_supplements": plan_dict.get("vitamins_and_supplements") or [],
        "chronotherapy_schedule": chronotherapy,
        "structured_tasks": structured_tasks,
        "doctor_comments": doctor_comments or plan_dict.get("doctor_remarks", ""),
        "approved_by": doctor_name if status == "approved" else None,
        "approved_at": now if status == "approved" else None,
        "created_at": now,
        "updated_at": now
    }

    with _WRITE_LOCK:
        plans = _read_json_direct(CARE_PLANS_FILE)
        # Determine version for patient
        patient_plans = [p for p in plans if normalize_email(p.get("patient_email")) == norm_email]
        if not plan_id:
            rec["version"] = len(patient_plans) + 1
        idx = next((i for i, p in enumerate(plans) if p.get("id") == pid), None)
        if idx is not None:
            plans[idx] = rec
        else:
            plans.insert(0, rec)
        _write_json_direct(CARE_PLANS_FILE, plans)

        # Also link back to assessment if exists
        if assessment_id:
            assessments = _read_json_direct(ASSESSMENTS_FILE)
            for a in assessments:
                if a.get("id") == assessment_id:
                    a["care_plan_id"] = pid
                    a["updated_at"] = now
                    break
            _write_json_direct(ASSESSMENTS_FILE, assessments)

    return rec


def get_care_plan_by_id(care_plan_id: str) -> Optional[Dict[str, Any]]:
    if not care_plan_id:
        return None
    with _WRITE_LOCK:
        plans = _read_json_direct(CARE_PLANS_FILE)
        for p in plans:
            if p.get("id") == care_plan_id:
                return dict(p)
    return None


def get_latest_care_plan_for_patient(patient_email: str) -> Optional[Dict[str, Any]]:
    norm_email = normalize_email(patient_email)
    if not norm_email:
        return None
    with _WRITE_LOCK:
        plans = _read_json_direct(CARE_PLANS_FILE)
        matching = [p for p in plans if normalize_email(p.get("patient_email")) == norm_email]
        if not matching:
            return None
        # Sort by updated_at / created_at descending
        matching.sort(key=lambda x: x.get("updated_at") or x.get("created_at") or "", reverse=True)
        return dict(matching[0])


def approve_care_plan(care_plan_id: str, doctor_name: str = "Attending Physician, MD") -> Optional[Dict[str, Any]]:
    now = _utc_now_iso()
    with _WRITE_LOCK:
        plans = _read_json_direct(CARE_PLANS_FILE)
        for p in plans:
            if p.get("id") == care_plan_id:
                p["status"] = "approved"
                p["approved_by"] = doctor_name
                p["approved_at"] = now
                p["updated_at"] = now
                _write_json_direct(CARE_PLANS_FILE, plans)
                return dict(p)
    return None


# ── Activity Completion Storage (data/activity_completions.json) ───────────────

def toggle_task_completion(
    patient_email: str,
    care_plan_id: str,
    task_id: str,
    calendar_date: str,
    completed: bool,
    category: str = "",
    title: str = ""
) -> Dict[str, Any]:
    norm_email = normalize_email(patient_email)
    cal_date = calendar_date or _today_date_str()
    now = _utc_now_iso()

    with _WRITE_LOCK:
        completions = _read_json_direct(COMPLETIONS_FILE)
        found = None
        for c in completions:
            if (
                normalize_email(c.get("patient_email")) == norm_email
                and c.get("task_id") == task_id
                and c.get("calendar_date") == cal_date
            ):
                found = c
                break

        if found:
            found["completed"] = bool(completed)
            found["completed_at"] = now if completed else None
            found["updated_at"] = now
            if category:
                found["category"] = category
            if title:
                found["title"] = title
            res = dict(found)
        else:
            res = {
                "id": f"cmp_{uuid.uuid4().hex[:10]}",
                "patient_email": norm_email,
                "care_plan_id": care_plan_id,
                "task_id": task_id,
                "calendar_date": cal_date,
                "category": category or "general",
                "title": title or task_id,
                "completed": bool(completed),
                "completed_at": now if completed else None,
                "created_at": now,
                "updated_at": now
            }
            completions.append(res)

        _write_json_direct(COMPLETIONS_FILE, completions)
        return res


def get_patient_daily_progress(patient_email: str, calendar_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Computes real daily schedule, completion states, and progress percentage for a specific date.
    Never fabricates tasks or fake completion counts.
    """
    norm_email = normalize_email(patient_email)
    cal_date = calendar_date or _today_date_str()

    plan = get_latest_care_plan_for_patient(norm_email)
    if not plan:
        return {
            "patient_email": norm_email,
            "calendar_date": cal_date,
            "care_plan_id": None,
            "care_plan_status": "none",
            "total_tasks": 0,
            "completed_tasks": 0,
            "completion_percentage": 0,
            "tasks": [],
            "message": "No care plan assigned for this patient yet."
        }

    raw_tasks = plan.get("structured_tasks") or []
    # Daily tasks only for daily routine view
    daily_tasks = [t for t in raw_tasks if t.get("cadence") == "daily"]

    with _WRITE_LOCK:
        completions = _read_json_direct(COMPLETIONS_FILE)
        # Map of task_id -> completion dict for this date
        comp_map = {
            c.get("task_id"): c
            for c in completions
            if normalize_email(c.get("patient_email")) == norm_email and c.get("calendar_date") == cal_date
        }

    items = []
    completed_count = 0
    exercise_completed = 0
    exercise_total = 0
    medication_completed = 0
    medication_total = 0

    for t in daily_tasks:
        tid = t.get("task_id")
        comp = comp_map.get(tid)
        is_done = bool(comp and comp.get("completed"))
        if is_done:
            completed_count += 1

        cat = (t.get("category") or "").lower()
        if cat == "exercise":
            exercise_total += 1
            if is_done:
                exercise_completed += 1
        elif cat == "medication":
            medication_total += 1
            if is_done:
                medication_completed += 1

        items.append({
            "task_id": tid,
            "care_plan_id": plan.get("id"),
            "period": t.get("period", "Daily"),
            "time": t.get("time", ""),
            "title": t.get("title", ""),
            "description": t.get("description", ""),
            "category": t.get("category", "general"),
            "icon": t.get("icon", "✓"),
            "completed": is_done,
            "completed_at": comp.get("completed_at") if comp else None
        })

    total = len(items)
    pct = int(round((completed_count / total * 100))) if total > 0 else 0

    return {
        "patient_email": norm_email,
        "calendar_date": cal_date,
        "care_plan_id": plan.get("id"),
        "care_plan_status": plan.get("status", "draft"),
        "care_plan_version": plan.get("version", 1),
        "approved_by": plan.get("approved_by"),
        "approved_at": plan.get("approved_at"),
        "total_tasks": total,
        "completed_tasks": completed_count,
        "completion_percentage": pct,
        "exercise_adherence": {
            "total": exercise_total,
            "completed": exercise_completed,
            "percentage": int(round((exercise_completed / exercise_total * 100))) if exercise_total > 0 else None
        },
        "medication_adherence": {
            "total": medication_total,
            "completed": medication_completed,
            "percentage": int(round((medication_completed / medication_total * 100))) if medication_total > 0 else None
        },
        "tasks": items,
        "diet": plan.get("diet"),
        "exercise": plan.get("exercise"),
        "doctor_comments": plan.get("doctor_comments", "")
    }


def get_patient_weekly_progress(patient_email: str, reference_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Computes 7-day adherence matrix (Monday to Sunday) for the week containing reference_date.
    """
    from datetime import timedelta
    norm_email = normalize_email(patient_email)
    ref = datetime.strptime(reference_date or _today_date_str(), "%Y-%m-%d").date()
    # Find Monday of that week
    monday = ref - timedelta(days=ref.weekday())

    plan = get_latest_care_plan_for_patient(norm_email)
    days_data = []
    total_week_tasks = 0
    completed_week_tasks = 0

    for i in range(7):
        day = monday + timedelta(days=i)
        day_str = day.strftime("%Y-%m-%d")
        day_name = day.strftime("%A")
        prog = get_patient_daily_progress(norm_email, calendar_date=day_str)
        total_week_tasks += prog.get("total_tasks", 0)
        completed_week_tasks += prog.get("completed_tasks", 0)
        days_data.append({
            "date": day_str,
            "day_name": day_name,
            "is_today": day_str == _today_date_str(),
            "total_tasks": prog.get("total_tasks", 0),
            "completed_tasks": prog.get("completed_tasks", 0),
            "percentage": prog.get("completion_percentage", 0)
        })

    week_pct = int(round((completed_week_tasks / total_week_tasks * 100))) if total_week_tasks > 0 else 0

    return {
        "patient_email": norm_email,
        "week_start": monday.strftime("%Y-%m-%d"),
        "week_end": (monday + timedelta(days=6)).strftime("%Y-%m-%d"),
        "care_plan_id": plan.get("id") if plan else None,
        "total_week_tasks": total_week_tasks,
        "completed_week_tasks": completed_week_tasks,
        "weekly_completion_percentage": week_pct,
        "days": days_data
    }


# ── Medication Storage (data/medications.json & data/medications/) ────────────

def save_medication_record(
    file_id: str,
    original_filename: str,
    file_path: str,
    patient_email: Optional[str] = None,
    assessment_id: Optional[str] = None,
    notes: Optional[str] = None,
    medications: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    norm_email = normalize_email(patient_email)
    now = _utc_now_iso()
    rec = {
        "file_id": file_id,
        "filename": original_filename,
        "file_path": str(file_path),
        "download_url": f"/api/medications/{file_id}/download",
        "patient_email": norm_email,
        "assessment_id": assessment_id or "",
        "notes": notes or "",
        "medications": medications or [],
        "uploaded_at": now
    }
    with _WRITE_LOCK:
        meds = _read_json_direct(MEDICATIONS_FILE)
        meds.append(rec)
        _write_json_direct(MEDICATIONS_FILE, meds)

        # Update assessment if assessment_id provided
        if assessment_id:
            assessments = _read_json_direct(ASSESSMENTS_FILE)
            for a in assessments:
                if a.get("id") == assessment_id:
                    a["medication_record"] = rec
                    break
            _write_json_direct(ASSESSMENTS_FILE, assessments)

        # Update patient if patient_email provided
        if norm_email:
            patients = _read_json_direct(PATIENTS_FILE)
            for p in patients:
                if normalize_email(p.get("email")) == norm_email:
                    p["medication_record"] = rec
                    break
            _write_json_direct(PATIENTS_FILE, patients)

    return rec


def get_medication_record(file_id: str) -> Optional[Dict[str, Any]]:
    if not file_id:
        return None
    with _WRITE_LOCK:
        meds = _read_json_direct(MEDICATIONS_FILE)
        for m in meds:
            if m.get("file_id") == file_id:
                return dict(m)
    return None


def get_patient_medications(patient_email: str) -> Optional[Dict[str, Any]]:
    norm_email = normalize_email(patient_email)
    if not norm_email:
        return None
    with _WRITE_LOCK:
        # Check patient first
        patients = _read_json_direct(PATIENTS_FILE)
        for p in patients:
            if normalize_email(p.get("email")) == norm_email:
                if p.get("medication_record"):
                    return dict(p["medication_record"])

        # Check medications list (latest first)
        meds = _read_json_direct(MEDICATIONS_FILE)
        for m in reversed(meds):
            if normalize_email(m.get("patient_email")) == norm_email:
                return dict(m)
    return None

