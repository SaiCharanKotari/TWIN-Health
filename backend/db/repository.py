"""
backend/db/repository.py — Data access layer for patients, assessments, reviews, care plans, and daily progress.
"""
from __future__ import annotations
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from db.database import get_db


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Patient Repository ─────────────────────────────────────────────────────────

def create_patient(
    name: str,
    age: Optional[int] = None,
    sex: Optional[str] = None,
    demographics: Optional[Dict[str, Any]] = None,
    patient_id: Optional[str] = None
) -> Dict[str, Any]:
    pid = patient_id or f"pat_{uuid.uuid4().hex[:10]}"
    now = _utc_now()
    demo_str = json.dumps(demographics or {})
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO patients (id, name, age, sex, demographics_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                age = excluded.age,
                sex = excluded.sex,
                demographics_json = excluded.demographics_json,
                updated_at = excluded.updated_at
            """,
            (pid, name, age, sex, demo_str, now, now)
        )
    return get_patient_by_id(pid)


def get_patient_by_id(patient_id: str) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
        if not row:
            return None
        res = dict(row)
        res["demographics"] = json.loads(res.pop("demographics_json") or "{}")
        return res


def list_patients(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM patients ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["demographics"] = json.loads(d.pop("demographics_json") or "{}")
            result.append(d)
        return result


# ── Assessment Repository ──────────────────────────────────────────────────────

def create_assessment(
    patient_id: str,
    inputs: Dict[str, Any],
    disease_results: Dict[str, Any],
    status: str = "draft",
    provider: str = "local",
    data_completeness: float = 0.0,
    warnings: Optional[List[str]] = None,
    normalized_inputs: Optional[Dict[str, Any]] = None,
    assessment_id: Optional[str] = None
) -> Dict[str, Any]:
    aid = assessment_id or f"asm_{uuid.uuid4().hex[:10]}"
    now = _utc_now()
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO assessments (
                id, patient_id, inputs_json, normalized_inputs_json,
                disease_results_json, status, provider, data_completeness,
                warnings_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                patient_id = excluded.patient_id,
                inputs_json = excluded.inputs_json,
                normalized_inputs_json = excluded.normalized_inputs_json,
                disease_results_json = excluded.disease_results_json,
                status = excluded.status,
                provider = excluded.provider,
                data_completeness = excluded.data_completeness,
                warnings_json = excluded.warnings_json,
                updated_at = excluded.updated_at
            """,
            (
                aid,
                patient_id,
                json.dumps(inputs),
                json.dumps(normalized_inputs or inputs),
                json.dumps(disease_results),
                status,
                provider,
                data_completeness,
                json.dumps(warnings or []),
                now,
                now
            )
        )
    return get_assessment_by_id(aid)


def get_assessment_by_id(assessment_id: str) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT a.*, p.name as patient_name, p.age as patient_age, p.sex as patient_sex
            FROM assessments a
            JOIN patients p ON a.patient_id = p.id
            WHERE a.id = ?
            """,
            (assessment_id,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["inputs"] = json.loads(d.pop("inputs_json") or "{}")
        d["normalized_inputs"] = json.loads(d.pop("normalized_inputs_json") or "{}")
        d["disease_results"] = json.loads(d.pop("disease_results_json") or "{}")
        d["warnings"] = json.loads(d.pop("warnings_json") or "[]")
        return d


def list_assessments_for_patient(patient_id: str) -> List[Dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM assessments WHERE patient_id = ? ORDER BY created_at DESC",
            (patient_id,)
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["inputs"] = json.loads(d.pop("inputs_json") or "{}")
            d["disease_results"] = json.loads(d.pop("disease_results_json") or "{}")
            result.append(d)
        return result


def update_assessment_status(assessment_id: str, new_status: str) -> None:
    now = _utc_now()
    with get_db() as conn:
        conn.execute(
            "UPDATE assessments SET status = ?, updated_at = ? WHERE id = ?",
            (new_status, now, assessment_id)
        )


# ── Clinical Review Repository ─────────────────────────────────────────────────

def create_or_update_review(
    assessment_id: str,
    doctor_name: str = "Dr. Sarah Mitchell, MD",
    status: str = "pending",
    doctor_notes: str = "",
    requested_tests: Optional[List[str]] = None,
    review_id: Optional[str] = None
) -> Dict[str, Any]:
    now = _utc_now()
    rid = review_id or f"rev_{uuid.uuid4().hex[:10]}"
    req_str = json.dumps(requested_tests or [])
    
    with get_db() as conn:
        existing = conn.execute("SELECT id FROM clinical_reviews WHERE assessment_id = ?", (assessment_id,)).fetchone()
        if existing:
            rid = existing["id"]
            conn.execute(
                """
                UPDATE clinical_reviews
                SET doctor_name = ?, status = ?, doctor_notes = ?, requested_tests_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (doctor_name, status, doctor_notes, req_str, now, rid)
            )
        else:
            conn.execute(
                """
                INSERT INTO clinical_reviews (id, assessment_id, doctor_name, status, doctor_notes, requested_tests_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (rid, assessment_id, doctor_name, status, doctor_notes, req_str, now, now)
            )
        
        # Keep assessment status aligned
        asm_status = "pending_review" if status == "pending" else "reviewed"
        conn.execute("UPDATE assessments SET status = ?, updated_at = ? WHERE id = ?", (asm_status, now, assessment_id))
        
    return get_review_by_assessment_id(assessment_id)


def get_review_by_assessment_id(assessment_id: str) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM clinical_reviews WHERE assessment_id = ?", (assessment_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["requested_tests"] = json.loads(d.pop("requested_tests_json") or "[]")
        return d


def list_doctor_queue(
    status_filter: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
    query = """
    SELECT 
        a.id as assessment_id,
        a.patient_id,
        a.status as assessment_status,
        a.provider,
        a.data_completeness,
        a.created_at as assessment_date,
        a.disease_results_json,
        p.name as patient_name,
        p.age as patient_age,
        p.sex as patient_sex,
        r.id as review_id,
        COALESCE(r.status, 'pending') as review_status,
        COALESCE(r.doctor_name, 'Unassigned') as doctor_name,
        COALESCE(r.doctor_notes, '') as doctor_notes,
        r.requested_tests_json,
        cp.id as care_plan_id,
        cp.status as care_plan_status
    FROM assessments a
    JOIN patients p ON a.patient_id = p.id
    LEFT JOIN clinical_reviews r ON a.id = r.assessment_id
    LEFT JOIN (
        SELECT id, assessment_id, status FROM care_plans 
        WHERE (assessment_id, version) IN (
            SELECT assessment_id, MAX(version) FROM care_plans GROUP BY assessment_id
        )
    ) cp ON a.id = cp.assessment_id
    WHERE 1=1
    """
    params: List[Any] = []

    if status_filter and status_filter.lower() != "all":
        if status_filter == "pending":
            query += " AND (r.status = 'pending' OR a.status = 'pending_review' OR r.status IS NULL)"
        elif status_filter == "reviewed":
            query += " AND r.status = 'reviewed'"
        elif status_filter == "follow_up_required":
            query += " AND r.status = 'follow_up_required'"

    if search:
        query += " AND (p.name LIKE ? OR a.id LIKE ? OR p.id LIKE ?)"
        s = f"%{search}%"
        params.extend([s, s, s])

    query += " ORDER BY a.created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            dis_res = json.loads(d.pop("disease_results_json") or "{}")
            # Extract high/moderate risk flags
            high_risks = []
            mod_risks = []
            for dis_name, dis_val in dis_res.items():
                if isinstance(dis_val, dict):
                    pred = dis_val.get("prediction")
                    if isinstance(pred, dict):
                        label = pred.get("label", "") or ""
                        pct = pred.get("percentage") or int(round((pred.get("probability") or 0) * 100))
                        title = dis_val.get("display_name", dis_name.replace("_", " ").title())
                        if "high" in label or pct >= 65:
                            high_risks.append({"disease": dis_name, "title": title, "pct": pct})
                        elif "mod" in label or pct >= 35:
                            mod_risks.append({"disease": dis_name, "title": title, "pct": pct})

            d["high_risks"] = high_risks
            d["mod_risks"] = mod_risks
            d["requested_tests"] = json.loads(d.pop("requested_tests_json") or "[]")
            results.append(d)
        return results


def get_dashboard_kpis() -> Dict[str, int]:
    with get_db() as conn:
        total_patients = conn.execute("SELECT COUNT(*) as cnt FROM patients").fetchone()["cnt"]
        total_assessments = conn.execute("SELECT COUNT(*) as cnt FROM assessments").fetchone()["cnt"]
        pending_reviews = conn.execute(
            """
            SELECT COUNT(*) as cnt FROM assessments a
            LEFT JOIN clinical_reviews r ON a.id = r.assessment_id
            WHERE r.status = 'pending' OR a.status = 'pending_review' OR (r.status IS NULL AND a.status != 'draft')
            """
        ).fetchone()["cnt"]
        reviewed_cases = conn.execute(
            "SELECT COUNT(*) as cnt FROM clinical_reviews WHERE status = 'reviewed'"
        ).fetchone()["cnt"]
        follow_up_cases = conn.execute(
            "SELECT COUNT(*) as cnt FROM clinical_reviews WHERE status = 'follow_up_required'"
        ).fetchone()["cnt"]
        approved_care_plans = conn.execute(
            "SELECT COUNT(*) as cnt FROM care_plans WHERE status = 'approved'"
        ).fetchone()["cnt"]

        return {
            "total_patients": total_patients,
            "total_assessments": total_assessments,
            "pending_reviews": pending_reviews,
            "reviewed_cases": reviewed_cases,
            "follow_up_cases": follow_up_cases,
            "approved_care_plans": approved_care_plans,
        }


# ── Care Plan Repository ───────────────────────────────────────────────────────

def create_or_update_care_plan(
    patient_id: str,
    assessment_id: Optional[str],
    diet: Dict[str, Any],
    exercise: Dict[str, Any],
    schedule: List[Dict[str, Any]],
    status: str = "draft",
    medications: Optional[List[Dict[str, Any]]] = None,
    lifestyle: Optional[Dict[str, Any]] = None,
    doctor_comments: str = "",
    plan_id: Optional[str] = None
) -> Dict[str, Any]:
    now = _utc_now()
    pid = plan_id or f"cpl_{uuid.uuid4().hex[:10]}"

    with get_db() as conn:
        # Determine version
        existing = conn.execute(
            "SELECT MAX(version) as max_v FROM care_plans WHERE patient_id = ?",
            (patient_id,)
        ).fetchone()
        version = (existing["max_v"] or 0) + 1 if not plan_id else 1

        conn.execute(
            """
            INSERT INTO care_plans (
                id, patient_id, assessment_id, version, status,
                diet_json, exercise_json, lifestyle_json, medications_json,
                schedule_json, doctor_comments, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                diet_json = excluded.diet_json,
                exercise_json = excluded.exercise_json,
                lifestyle_json = excluded.lifestyle_json,
                medications_json = excluded.medications_json,
                schedule_json = excluded.schedule_json,
                doctor_comments = excluded.doctor_comments,
                status = excluded.status,
                updated_at = excluded.updated_at
            """,
            (
                pid,
                patient_id,
                assessment_id,
                version,
                status,
                json.dumps(diet),
                json.dumps(exercise),
                json.dumps(lifestyle or {}),
                json.dumps(medications or []),
                json.dumps(schedule),
                doctor_comments,
                now,
                now
            )
        )
    return get_care_plan_by_id(pid)


def approve_care_plan(care_plan_id: str, approved_by: str = "Dr. Sarah Mitchell, MD") -> Dict[str, Any]:
    now = _utc_now()
    with get_db() as conn:
        # Fetch patient ID for this plan
        row = conn.execute("SELECT patient_id, assessment_id FROM care_plans WHERE id = ?", (care_plan_id,)).fetchone()
        if not row:
            raise ValueError(f"Care plan {care_plan_id} not found")
        
        patient_id = row["patient_id"]
        asm_id = row["assessment_id"]

        # Archive previously approved plans for this patient
        conn.execute(
            "UPDATE care_plans SET status = 'archived', updated_at = ? WHERE patient_id = ? AND status = 'approved'",
            (now, patient_id)
        )

        # Set this plan to approved
        conn.execute(
            """
            UPDATE care_plans
            SET status = 'approved', approved_by = ?, approved_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (approved_by, now, now, care_plan_id)
        )

        # Update assessment status if linked
        if asm_id:
            conn.execute(
                "UPDATE assessments SET status = 'care_plan_approved', updated_at = ? WHERE id = ?",
                (now, asm_id)
            )

    return get_care_plan_by_id(care_plan_id)


def get_care_plan_by_id(care_plan_id: str) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM care_plans WHERE id = ?", (care_plan_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["diet"] = json.loads(d.pop("diet_json") or "{}")
        d["exercise"] = json.loads(d.pop("exercise_json") or "{}")
        d["lifestyle"] = json.loads(d.pop("lifestyle_json") or "{}")
        d["medications"] = json.loads(d.pop("medications_json") or "[]")
        d["schedule"] = json.loads(d.pop("schedule_json") or "[]")
        return d


def get_latest_approved_care_plan(patient_id: str) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT * FROM care_plans
            WHERE patient_id = ? AND status = 'approved'
            ORDER BY version DESC, updated_at DESC LIMIT 1
            """,
            (patient_id,)
        ).fetchone()
        if not row:
            # Fallback to latest draft if no approved plan
            row = conn.execute(
                """
                SELECT * FROM care_plans
                WHERE patient_id = ?
                ORDER BY version DESC, updated_at DESC LIMIT 1
                """,
                (patient_id,)
            ).fetchone()
            if not row:
                return None

        d = dict(row)
        d["diet"] = json.loads(d.pop("diet_json") or "{}")
        d["exercise"] = json.loads(d.pop("exercise_json") or "{}")
        d["lifestyle"] = json.loads(d.pop("lifestyle_json") or "{}")
        d["medications"] = json.loads(d.pop("medications_json") or "[]")
        d["schedule"] = json.loads(d.pop("schedule_json") or "[]")
        return d


def list_care_plans_for_patient(patient_id: str) -> List[Dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM care_plans WHERE patient_id = ? ORDER BY version DESC",
            (patient_id,)
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["diet"] = json.loads(d.pop("diet_json") or "{}")
            d["exercise"] = json.loads(d.pop("exercise_json") or "{}")
            d["lifestyle"] = json.loads(d.pop("lifestyle_json") or "{}")
            d["medications"] = json.loads(d.pop("medications_json") or "[]")
            d["schedule"] = json.loads(d.pop("schedule_json") or "[]")
            result.append(d)
        return result


# ── Daily Progress Repository ──────────────────────────────────────────────────

def toggle_daily_task_completion(
    patient_id: str,
    care_plan_id: str,
    calendar_date: str,
    task_id: str,
    category: str,
    label: str,
    completed: bool,
    notes: str = ""
) -> Dict[str, Any]:
    now = _utc_now()
    comp_val = 1 if completed else 0
    comp_at = now if completed else None
    prog_id = f"prg_{uuid.uuid4().hex[:10]}"

    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO daily_progress (
                id, patient_id, care_plan_id, calendar_date, task_id,
                category, label, completed, completed_at, notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(patient_id, care_plan_id, calendar_date, task_id) DO UPDATE SET
                completed = excluded.completed,
                completed_at = excluded.completed_at,
                notes = excluded.notes,
                updated_at = excluded.updated_at
            """,
            (
                prog_id, patient_id, care_plan_id, calendar_date, task_id,
                category, label, comp_val, comp_at, notes, now, now
            )
        )

        row = conn.execute(
            """
            SELECT * FROM daily_progress
            WHERE patient_id = ? AND care_plan_id = ? AND calendar_date = ? AND task_id = ?
            """,
            (patient_id, care_plan_id, calendar_date, task_id)
        ).fetchone()
        return dict(row)


def get_daily_progress_for_date(
    patient_id: str,
    calendar_date: str,
    care_plan_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    with get_db() as conn:
        if care_plan_id:
            rows = conn.execute(
                """
                SELECT * FROM daily_progress
                WHERE patient_id = ? AND care_plan_id = ? AND calendar_date = ?
                """,
                (patient_id, care_plan_id, calendar_date)
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM daily_progress
                WHERE patient_id = ? AND calendar_date = ?
                """,
                (patient_id, calendar_date)
            ).fetchall()
        return [dict(r) for r in rows]


def get_weekly_progress_summary(patient_id: str) -> Dict[str, Any]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT 
                calendar_date,
                COUNT(*) as total_logged,
                SUM(completed) as total_completed
            FROM daily_progress
            WHERE patient_id = ?
            GROUP BY calendar_date
            ORDER BY calendar_date DESC
            LIMIT 7
            """,
            (patient_id,)
        ).fetchall()
        return {
            "patient_id": patient_id,
            "days": [
                {
                    "date": r["calendar_date"],
                    "total_logged": r["total_logged"],
                    "total_completed": r["total_completed"],
                    "percentage": int(round((r["total_completed"] / r["total_logged"]) * 100)) if r["total_logged"] else 0
                }
                for r in rows
            ]
        }
