"""
tests/test_db_persistence.py — Automated verification for SQLite persistence layer.
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from db.database import init_db
from db import repository as repo


def setup_module():
    init_db()


def test_patient_crud():
    pat = repo.create_patient(
        name="Test Patient A",
        age=45,
        sex="female",
        demographics={"test": True},
        patient_id="test_pat_crud"
    )
    assert pat["id"] == "test_pat_crud"
    assert pat["name"] == "Test Patient A"
    assert pat["demographics"]["test"] is True

    fetched = repo.get_patient_by_id("test_pat_crud")
    assert fetched is not None
    assert fetched["age"] == 45


def test_assessment_crud_and_linking():
    pat = repo.create_patient(name="Test Assessment Patient", patient_id="test_pat_asm")
    asm = repo.create_assessment(
        patient_id=pat["id"],
        inputs={"age": 50, "systolic_bp": 130},
        disease_results={"diabetes": {"status": "success", "prediction": {"percentage": 25}}},
        status="draft",
        provider="local",
        assessment_id="test_asm_01"
    )

    assert asm["id"] == "test_asm_01"
    assert asm["patient_id"] == "test_pat_asm"
    assert asm["status"] == "draft"

    fetched = repo.get_assessment_by_id("test_asm_01")
    assert fetched is not None
    assert fetched["inputs"]["age"] == 50
    assert fetched["disease_results"]["diabetes"]["status"] == "success"


def test_clinical_review_lifecycle():
    pat = repo.create_patient(name="Test Review Patient", patient_id="test_pat_rev")
    asm = repo.create_assessment(
        patient_id=pat["id"],
        inputs={"age": 55},
        disease_results={},
        status="pending_review",
        assessment_id="test_asm_rev"
    )

    # Initial submission creates pending review
    rev = repo.create_or_update_review(
        assessment_id=asm["id"],
        doctor_name="Dr. Sarah Mitchell, MD",
        status="pending",
        doctor_notes="",
        requested_tests=[]
    )
    assert rev["status"] == "pending"

    # Clinician update
    updated = repo.create_or_update_review(
        assessment_id=asm["id"],
        doctor_name="Dr. Sarah Mitchell, MD",
        status="reviewed",
        doctor_notes="Patient vitals reviewed. Maintain glycemic targets.",
        requested_tests=["Repeat HbA1c"]
    )
    assert updated["status"] == "reviewed"
    assert "Repeat HbA1c" in updated["requested_tests"]
    assert "glycemic" in updated["doctor_notes"]


def test_care_plan_versioning_and_approval():
    pat = repo.create_patient(name="Test Plan Patient", patient_id="test_pat_plan")
    
    # Version 1 (Draft)
    plan1 = repo.create_or_update_care_plan(
        patient_id=pat["id"],
        assessment_id=None,
        diet={"foods_to_eat": ["Oats"]},
        exercise={"protocol": "Walking"},
        schedule=[{"time": "08:00 AM", "task": "Breakfast"}],
        status="draft",
        plan_id="test_plan_v1"
    )
    assert plan1["status"] == "draft"

    # Approve Version 1
    approved = repo.approve_care_plan("test_plan_v1", approved_by="Dr. Sarah Mitchell, MD")
    assert approved["status"] == "approved"
    assert approved["approved_by"] == "Dr. Sarah Mitchell, MD"

    # Latest approved plan should be test_plan_v1
    current = repo.get_latest_approved_care_plan(pat["id"])
    assert current["id"] == "test_plan_v1"


def test_daily_progress_toggle_and_date_awareness():
    pat = repo.create_patient(name="Test Progress Patient", patient_id="test_pat_prog")
    plan = repo.create_or_update_care_plan(
        patient_id=pat["id"],
        assessment_id=None,
        diet={},
        exercise={},
        schedule=[],
        status="approved",
        plan_id="test_plan_prog"
    )

    date1 = "2026-10-13"
    date2 = "2026-10-14"

    # Toggle task on date1
    t1 = repo.toggle_daily_task_completion(
        patient_id=pat["id"],
        care_plan_id=plan["id"],
        calendar_date=date1,
        task_id="task_morning_walk",
        category="exercise",
        label="Morning 30-min walk",
        completed=True
    )
    assert t1["completed"] == 1

    # Date 1 has 1 completed task
    prog1 = repo.get_daily_progress_for_date(pat["id"], date1)
    assert len(prog1) == 1
    assert prog1[0]["completed"] == 1

    # Date 2 has 0 tasks logged
    prog2 = repo.get_daily_progress_for_date(pat["id"], date2)
    assert len(prog2) == 0

    # Uncheck task on date1
    t1_off = repo.toggle_daily_task_completion(
        patient_id=pat["id"],
        care_plan_id=plan["id"],
        calendar_date=date1,
        task_id="task_morning_walk",
        category="exercise",
        label="Morning 30-min walk",
        completed=False
    )
    assert t1_off["completed"] == 0
