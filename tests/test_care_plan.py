"""
tests/test_care_plan.py — Unit and integration tests for the Personalized Care Plan & Prescription engine.
"""
import io
import pytest
from httpx import AsyncClient, ASGITransport
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
from main import app
from services.care_plan_service import generate_care_plan
from services.prescription_service import parse_prescription_receipt


@pytest.mark.asyncio
async def test_generate_care_plan_direct():
    patient = {
        "age": 47,
        "sex": "male",
        "bmi": 28.4,
        "fasting_glucose": 108.0,
        "systolic_bp": 138.0,
        "diastolic_bp": 88.0
    }
    results = {
        "diabetes": {
            "prediction": {"percentage": 45, "label": "moderate_risk"},
            "display_name": "Type 2 Diabetes",
            "explanation": {"factors": ["glucose: 108.0", "bmi: 28.4"]}
        },
        "liver_disease": {
            "prediction": {"percentage": 70, "label": "high_risk"},
            "display_name": "Liver Disease",
            "explanation": {"factors": ["alt: 65.0", "ast: 58.0"]}
        }
    }
    doctor_comments = "Strict glycemic monitoring and liver-friendly nutrition."

    plan = await generate_care_plan(patient, results, doctor_comments)
    assert plan is not None
    assert "diet" in plan
    assert "exercise" in plan
    assert "vitamins_and_supplements" in plan
    assert "chronotherapy_schedule" in plan
    assert len(plan["diet"]["foods_to_eat"]) > 0
    assert len(plan["diet"]["foods_to_avoid"]) > 0
    assert len(plan["chronotherapy_schedule"]) >= 8


@pytest.mark.asyncio
async def test_care_plan_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {
            "patient_data": {"age": 52, "sex": "female", "bmi": 31.0},
            "disease_results": {
                "heart_disease": {
                    "prediction": {"percentage": 60, "label": "moderate_risk"},
                    "display_name": "Heart Disease"
                }
            },
            "doctor_comments": "Moderate sodium intake."
        }
        res = await ac.post("/api/detection/care-plan", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert "diet" in data
        assert "exercise" in data
        assert "chronotherapy_schedule" in data


@pytest.mark.asyncio
async def test_prescription_upload_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        file_content = b"Simulated prescription content: Metformin 500mg BID, Atorvastatin 10mg HS"
        files = {"file": ("prescription.jpg", io.BytesIO(file_content), "image/jpeg")}
        res = await ac.post("/api/detection/prescription/upload", files=files)
        assert res.status_code == 200
        data = res.json()
        assert "medications" in data
        assert len(data["medications"]) > 0
