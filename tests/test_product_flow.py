"""
tests/test_product_flow.py — End-to-end integration test of full product flow:
1. Doctor logs in via /api/auth/demo-login
2. Doctor assesses patient with patient_email via /api/detection/analyze
3. Assessment is persisted to data/assessments.json and retrievable via /api/assessments/{id}
4. Patient logs in with the SAME email and retrieves daily schedule
5. Patient toggles task completion (exercise, hydration, etc.)
6. Doctor checks activity summary and sees patient-reported completion
7. Different patient isolation verification
"""
import os
import sys
import pytest
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

import uuid
from main import app
from storage import json_storage as js


@pytest.mark.asyncio
async def test_full_doctor_patient_product_flow():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Step 1: Doctor Login
        doc_login_res = await client.post("/api/auth/demo-login", json={
            "email": "doctor.smith@clinic.demo",
            "role": "doctor",
            "display_name": "Dr. Smith"
        })
        assert doc_login_res.status_code == 200
        doc_data = doc_login_res.json()
        assert doc_data["role"] == "doctor"
        assert doc_data["redirect_url"] == "/input"

        # Step 2: Doctor Assesses Patient
        target_patient_email = f"patient.charlie.{uuid.uuid4().hex[:6]}@example.com"
        assessment_payload = {
            "patient_email": target_patient_email,
            "doctor_email": "doctor.smith@clinic.demo",
            "name": "Charlie Miller",
            "age": 54,
            "sex": "male",
            "height_cm": 178,
            "weight_kg": 85,
            "systolic_bp": 142,
            "diastolic_bp": 90,
            "fasting_glucose": 126,
            "hba1c": 6.8,
            "total_cholesterol": 220,
            "hdl": 42,
            "ldl": 140,
            "triglycerides": 190,
            "egfr": 78,
            "creatinine": 1.15,
            "alt": 38,
            "ast": 32
        }

        analyze_res = await client.post("/api/detection/analyze?provider=local", json=assessment_payload)
        assert analyze_res.status_code == 200
        an_data = analyze_res.json()

        assessment_id = an_data.get("assessment_id")
        assert assessment_id is not None
        assert an_data.get("patient_email") == target_patient_email
        assert an_data["summary"]["models_run"] == 5

        # Step 3: Fetch Persisted Assessment by ID
        get_asm_res = await client.get(f"/api/assessments/{assessment_id}")
        assert get_asm_res.status_code == 200
        asm_record = get_asm_res.json()
        assert asm_record["id"] == assessment_id
        assert asm_record["patient_email"] == target_patient_email
        assert "diabetes" in asm_record["disease_results"]

        # Step 4: Patient Signs In with the SAME Email
        pat_login_res = await client.post("/api/auth/demo-login", json={
            "email": target_patient_email,
            "role": "patient"
        })
        assert pat_login_res.status_code == 200
        assert pat_login_res.json()["redirect_url"] == "/patient"

        # Step 5: Patient Retrieves Schedule
        test_date = "2026-10-14"
        sched_res = await client.get(f"/api/activity/patient/{target_patient_email}?date={test_date}")
        assert sched_res.status_code == 200
        sched_data = sched_res.json()

        assert sched_data["care_plan_id"] is not None
        assert sched_data["total_tasks"] > 0
        assert sched_data["completed_tasks"] == 0
        assert sched_data["completion_percentage"] == 0

        # Step 6: Patient Marks First Task (Exercise or Hydration) Complete
        first_task = sched_data["tasks"][0]
        toggle_res = await client.post("/api/activity/toggle", json={
            "patient_email": target_patient_email,
            "care_plan_id": sched_data["care_plan_id"],
            "task_id": first_task["task_id"],
            "calendar_date": test_date,
            "completed": True,
            "category": first_task["category"],
            "title": first_task["title"]
        })
        assert toggle_res.status_code == 200
        t_data = toggle_res.json()
        assert t_data["task"]["completed"] is True
        assert t_data["daily_progress"]["completed_tasks"] == 1
        assert t_data["daily_progress"]["completion_percentage"] > 0

        # Step 7: Doctor Checks Activity Monitor
        doc_activity_res = await client.get(
            f"/api/activity/doctor-summary?patientEmail={target_patient_email}&assessmentId={assessment_id}&date={test_date}"
        )
        assert doc_activity_res.status_code == 200
        doc_act_data = doc_activity_res.json()

        assert doc_act_data["daily"]["completed_tasks"] == 1
        # Confirm the task marked complete has completed=True
        matched = [t for t in doc_act_data["daily"]["tasks"] if t["task_id"] == first_task["task_id"]]
        assert len(matched) == 1
        assert matched[0]["completed"] is True

        # Step 8: Verify Isolation - Second Patient Has Independent Schedule
        other_patient_email = "patient.diana@example.com"
        other_res = await client.get(f"/api/activity/patient/{other_patient_email}?date={test_date}")
        assert other_res.status_code == 200
        # Other patient has not been assessed / has 0 tasks completed
        assert other_res.json()["completed_tasks"] == 0
