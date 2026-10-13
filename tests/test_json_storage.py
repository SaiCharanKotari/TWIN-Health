"""
tests/test_json_storage.py — Unit tests for thread-safe local JSON persistence layer.
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from storage import json_storage as js


def setup_module():
    js.init_storage()


def test_email_normalization():
    assert js.normalize_email("  User.Test@Example.COM ") == "user.test@example.com"
    assert js.normalize_email("JOHN@DEMO.ORG") == "john@demo.org"
    assert js.normalize_email(None) == ""


def test_user_upsert_and_retrieval():
    u = js.upsert_user("  Doctor.Alice@Hospital.org ", role="doctor", display_name="Dr. Alice Smith")
    assert u["email"] == "doctor.alice@hospital.org"
    assert u["role"] == "doctor"
    assert u["display_name"] == "Dr. Alice Smith"

    # Fetch with mixed case
    fetched = js.get_user_by_email("DOCTOR.ALICE@HOSPITAL.ORG")
    assert fetched is not None
    assert fetched["display_name"] == "Dr. Alice Smith"


def test_patient_upsert_and_isolation():
    p1 = js.upsert_patient("patient.one@test.com", name="Patient One", age=45, sex="female")
    p2 = js.upsert_patient("patient.two@test.com", name="Patient Two", age=62, sex="male")

    assert p1["id"] != p2["id"]
    assert p1["email"] == "patient.one@test.com"
    assert p2["email"] == "patient.two@test.com"

    # Updating patient one does not affect patient two
    js.upsert_patient("patient.one@test.com", age=46)
    p1_updated = js.get_patient_by_email("patient.one@test.com")
    p2_check = js.get_patient_by_email("patient.two@test.com")

    assert p1_updated["age"] == 46
    assert p2_check["age"] == 62


def test_assessment_creation_and_retrieval():
    asm = js.create_assessment(
        patient_id="pat_test_01",
        patient_email="patient.asm@test.com",
        doctor_email="doc@test.com",
        inputs={"age": 50, "systolic_bp": 135},
        disease_results={"diabetes": {"status": "success", "prediction": {"percentage": 30}}},
        data_completeness=0.85,
        assessment_id="asm_unit_test_01"
    )

    assert asm["id"] == "asm_unit_test_01"
    assert asm["patient_email"] == "patient.asm@test.com"

    fetched = js.get_assessment_by_id("asm_unit_test_01")
    assert fetched is not None
    assert fetched["inputs"]["age"] == 50
    assert fetched["disease_results"]["diabetes"]["prediction"]["percentage"] == 30


def test_care_plan_and_activity_lifecycle():
    plan_dict = {
        "title": "Unit Test Care Plan",
        "exercise": {"weekly_goal_mins": 120},
        "chronotherapy_schedule": [
            {"task_id": "t_walk", "time": "08:00 AM", "period": "Morning", "category": "exercise", "title": "Morning Walk", "action": "Walk 30 mins"},
            {"task_id": "t_water", "time": "11:00 AM", "period": "Midday", "category": "hydration", "title": "Hydration", "action": "Drink 500ml"}
        ]
    }

    cpl = js.create_or_update_care_plan(
        patient_email="active.patient@test.com",
        patient_id="pat_active",
        assessment_id="asm_unit_test_01",
        plan_dict=plan_dict,
        status="approved",
        plan_id="cpl_unit_test"
    )

    assert cpl["id"] == "cpl_unit_test"
    assert len(cpl["structured_tasks"]) >= 2

    # Initial progress: 0%
    prog = js.get_patient_daily_progress("active.patient@test.com", calendar_date="2026-10-14")
    assert prog["total_tasks"] == 2
    assert prog["completed_tasks"] == 0
    assert prog["completion_percentage"] == 0

    # Mark walk complete
    js.toggle_task_completion(
        patient_email="active.patient@test.com",
        care_plan_id="cpl_unit_test",
        task_id="t_walk",
        calendar_date="2026-10-14",
        completed=True
    )

    prog_after = js.get_patient_daily_progress("active.patient@test.com", calendar_date="2026-10-14")
    assert prog_after["completed_tasks"] == 1
    assert prog_after["completion_percentage"] == 50
    assert prog_after["exercise_adherence"]["completed"] == 1

    # Uncheck walk (idempotency check)
    js.toggle_task_completion(
        patient_email="active.patient@test.com",
        care_plan_id="cpl_unit_test",
        task_id="t_walk",
        calendar_date="2026-10-14",
        completed=False
    )

    prog_uncheck = js.get_patient_daily_progress("active.patient@test.com", calendar_date="2026-10-14")
    assert prog_uncheck["completed_tasks"] == 0
    assert prog_uncheck["completion_percentage"] == 0
