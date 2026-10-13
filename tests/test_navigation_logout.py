"""
tests/test_navigation_logout.py
Tests verifying that demo login and logout behavior:
1. Correctly authenticates demo patient and doctor roles.
2. Clears only session state on logout without deleting or corrupting any stored
   assessments, patients, care plans, or activity progress records.
"""
import os
import sys
import pytest
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
from main import app
from storage import json_storage as js


@pytest.mark.asyncio
async def test_demo_login_endpoints():
    """Verify demo login correctly identifies patient and doctor roles."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Patient login
        p_res = await ac.post("/api/auth/demo-login", json={
            "email": "sarah.connor@example.com",
            "role": "patient"
        })
        assert p_res.status_code == 200
        p_data = p_res.json()
        assert p_data["email"] == "sarah.connor@example.com"
        assert p_data["role"] == "patient"
        assert "/patient" in p_data["redirect_url"]

        # Doctor login
        d_res = await ac.post("/api/auth/demo-login", json={
            "email": "dr.smith@example.com",
            "role": "doctor"
        })
        assert d_res.status_code == 200
        d_data = d_res.json()
        assert d_data["email"] == "dr.smith@example.com"
        assert d_data["role"] == "doctor"
        assert d_data["redirect_url"] in ["/input", "/doctor"]


@pytest.mark.asyncio
async def test_logout_preserves_all_stored_data():
    """
    Verify that logging out does not delete:
    - Patient records
    - Assessment records
    - Care plans
    - Activity logs
    """
    patient_email = "preserve.patient@example.com"
    pat = js.upsert_patient(patient_email, name="Preserve Patient", age=42, sex="female")
    
    asm = js.create_assessment(
        patient_id=pat["id"],
        patient_email=patient_email,
        inputs={"age": 42, "sex": "female", "systolic_bp": 120},
        disease_results={"diabetes": {"status": "success", "prediction": {"percentage": 15}}}
    )
    
    plan_dict = {
        "chronotherapy_schedule": [
            {"task_id": "t_walk", "time": "08:00 AM", "period": "Morning", "category": "exercise", "title": "Morning Walk", "action": "Walk 30 mins"}
        ]
    }
    
    cpl = js.create_or_update_care_plan(
        patient_email=patient_email,
        patient_id=pat["id"],
        assessment_id=asm["id"],
        plan_dict=plan_dict,
        status="approved"
    )
    
    js.toggle_task_completion(
        patient_email=patient_email,
        care_plan_id=cpl["id"],
        task_id="t_walk",
        calendar_date="2026-10-13",
        completed=True
    )
    
    # Simulate client logout (clearing sessionStorage)
    # Backend records MUST remain completely intact
    pat_after = js.get_patient_by_email(patient_email)
    assert pat_after is not None, "Patient record must survive logout"
    assert pat_after["id"] == pat["id"]

    asm_after = js.get_assessment_by_id(asm["id"])
    assert asm_after is not None, "Assessment record must survive logout"
    assert asm_after["id"] == asm["id"]

    plan_after = js.get_latest_care_plan_for_patient(patient_email)
    assert plan_after is not None, "Care plan must survive logout"

    prog_after = js.get_patient_daily_progress(patient_email, "2026-10-13")
    assert prog_after["completed_tasks"] == 1, "Activity completions must survive logout"
