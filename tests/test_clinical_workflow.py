"""
tests/test_clinical_workflow.py — Full end-to-end clinical workflow integration test.
Tests:
Intake -> Persist -> Submit Review -> Doctor Review -> Draft Care Plan -> Approve Plan -> Patient View -> Checkoff Task.
"""
import os
import sys
import pytest
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
from main import app
from db.database import init_db


@pytest.mark.asyncio
async def test_full_clinical_workflow_lifecycle():
    init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:

        # 1. Check health & models health endpoint
        h_res = await ac.get("/api/models/health")
        assert h_res.status_code == 200
        h_data = h_res.json()
        assert h_data["all_pipelines_operational"] is True
        assert len(h_data["models"]) == 5

        # 2. Patient Intake & Detection (/api/assessments/run)
        intake_payload = {
            "patient_name": "Integration Test Patient",
            "provider": "local",
            "data": {
                "age": 58,
                "sex": "male",
                "height_cm": 172,
                "weight_kg": 88,
                "systolic_bp": 148.0,
                "diastolic_bp": 92.0,
                "fasting_glucose": 138.0,
                "total_cholesterol": 230.0,
                "creatinine": 1.2,
                "egfr": 70.0,
                "alt": 42.0,
                "ast": 38.0
            }
        }
        run_res = await ac.post("/api/assessments/run", json=intake_payload)
        assert run_res.status_code == 200
        run_data = run_res.json()
        asm_id = run_data["assessment_id"]
        pat_id = run_data["patient_id"]
        assert asm_id.startswith("asm_")
        assert run_data["detection"]["results"]["diabetes"]["status"] == "success"

        # 3. Patient Handoff: Submit for Doctor Review (/api/reviews/submit)
        submit_res = await ac.post("/api/reviews/submit", json={"assessment_id": asm_id})
        assert submit_res.status_code == 200
        sub_data = submit_res.json()
        assert sub_data["status"] == "pending_review"

        # 4. Doctor Queue (/api/reviews/queue)
        queue_res = await ac.get("/api/reviews/queue?status=pending")
        assert queue_res.status_code == 200
        q_data = queue_res.json()
        assert any(c["assessment_id"] == asm_id for c in q_data["cases"])

        # 5. Doctor Review Inspector (/api/assessments/{asm_id})
        asm_fetch = await ac.get(f"/api/assessments/{asm_id}")
        assert asm_fetch.status_code == 200
        asm_record = asm_fetch.json()
        assert asm_record["patient_id"] == pat_id
        assert asm_record["inputs"]["fasting_glucose"] == 138.0

        # 6. Doctor Updates Review & Notes (/api/reviews/{asm_id}/update)
        review_update = {
            "status": "reviewed",
            "doctor_notes": "Clinical review confirmed elevated postprandial glucose and stage 1 hypertension. Starting lifestyle intervention.",
            "requested_tests": ["Repeat HbA1c", "24-hr Ambulatory BP"],
            "doctor_name": "Dr. Sarah Mitchell, MD"
        }
        rev_res = await ac.post(f"/api/reviews/{asm_id}/update", json=review_update)
        assert rev_res.status_code == 200
        assert rev_res.json()["status"] == "reviewed"

        # 7. Doctor Drafts Care Plan (/api/care-plans/draft)
        draft_res = await ac.post("/api/care-plans/draft", json={
            "assessment_id": asm_id,
            "doctor_comments": "Strict low-sodium and glycemic control.",
            "provider": "local"
        })
        assert draft_res.status_code == 200
        draft_plan = draft_res.json()
        plan_id = draft_plan["id"]
        assert draft_plan["status"] == "draft"
        assert len(draft_plan["schedule"]) > 0

        # 8. Doctor Approves & Publishes Plan (/api/care-plans/{plan_id}/approve)
        approve_res = await ac.post(f"/api/care-plans/{plan_id}/approve", json={"approved_by": "Dr. Sarah Mitchell, MD"})
        assert approve_res.status_code == 200
        app_data = approve_res.json()
        assert app_data["care_plan"]["status"] == "approved"

        # 9. Patient Dashboard Views Approved Plan (/api/progress/{pat_id})
        prog_res = await ac.get(f"/api/progress/{pat_id}?date=2026-10-13")
        assert prog_res.status_code == 200
        p_data = prog_res.json()
        assert p_data["care_plan_status"] == "approved"
        assert p_data["approved_by"] == "Dr. Sarah Mitchell, MD"
        assert len(p_data["tasks"]) > 0

        # 10. Patient Checks off a Task (/api/progress/toggle)
        first_task = p_data["tasks"][0]
        toggle_res = await ac.post("/api/progress/toggle", json={
            "patient_id": pat_id,
            "care_plan_id": plan_id,
            "calendar_date": "2026-10-13",
            "task_id": first_task["task_id"],
            "category": first_task["category"],
            "label": first_task["label"],
            "completed": True
        })
        assert toggle_res.status_code == 200

        # 11. Verify reload preserves task completion state
        reload_res = await ac.get(f"/api/progress/{pat_id}?date=2026-10-13")
        r_data = reload_res.json()
        assert r_data["completed_tasks"] == 1
        assert r_data["tasks"][0]["completed"] is True
        assert r_data["completion_percentage"] > 0
