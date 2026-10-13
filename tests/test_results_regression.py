"""
tests/test_results_regression.py
Regression tests for GET /api/assessments/{id} and results route payload contract.
Guarantees the 'Cannot read properties of undefined (reading age)' crash is permanently prevented.
"""
import os
import sys
import pytest
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
from main import app
from routes.clinical import normalize_assessment_record
from storage import json_storage as js


@pytest.mark.asyncio
async def test_get_assessment_asm_6c72fced1e_exact_regression():
    """
    Exact reproduction test for the assessment reported in the regression:
    Failing URL: http://localhost:8000/results?assessmentId=asm_6c72fced1e
    Must return 200 with normalized patient_summary containing 'age', and results dictionary.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/assessments/asm_6c72fced1e")
        assert response.status_code == 200, f"Expected 200 for asm_6c72fced1e, got {response.status_code}"
        
        data = response.json()
        assert data["id"] == "asm_6c72fced1e"
        
        # Verify patient_summary exists and has age (the field that crashed the UI)
        assert "patient_summary" in data, "patient_summary must be present in assessment response"
        assert isinstance(data["patient_summary"], dict)
        assert data["patient_summary"].get("age") == 47, f"Expected age 47, got {data['patient_summary'].get('age')}"
        assert data["patient_summary"].get("sex") == "male"
        assert data["patient_summary"].get("bmi") == 28.4
        
        # Verify results object exists and has the 5 disease results
        assert "results" in data, "results must be present in assessment response"
        assert isinstance(data["results"], dict)
        for disease in ["diabetes", "heart_disease", "ckd", "liver_disease", "stroke"]:
            assert disease in data["results"], f"Disease '{disease}' missing in normalized results"
            res = data["results"][disease]
            assert "prediction" in res
            assert "risk_score" in res or "risk_percent" in res or "prediction" in res


@pytest.mark.asyncio
async def test_get_assessment_not_found():
    """
    A nonexistent assessment ID must return 404 with a clear error detail,
    allowing the frontend to render the error state gracefully without crashing.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/assessments/asm_nonexistent_999999")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()


def test_normalize_assessment_record_legacy_payload():
    """
    Test that normalize_assessment_record handles arbitrary legacy structures:
    - Raw dict with only 'inputs' and 'disease_results'
    - Missing patient_summary
    - Missing results
    - Ensures patient_summary is never None or undefined
    """
    raw_legacy = {
        "id": "asm_legacy_test",
        "patient_email": "legacy.user@example.com",
        "inputs": {
            "age": 52,
            "sex": "female",
            "systolic_bp": 130,
            "fasting_glucose": 110,
        },
        "disease_results": {
            "diabetes": {
                "prediction": {"label": "moderate", "percentage": 42.0},
                "status": "success",
            }
        }
    }
    
    normalized = normalize_assessment_record(raw_legacy)
    assert "patient_summary" in normalized
    assert normalized["patient_summary"]["age"] == 52
    assert normalized["patient_summary"]["sex"] == "female"
    assert "results" in normalized
    assert "diabetes" in normalized["results"]
    assert "summary" in normalized
    assert "disclaimer" in normalized


def test_normalize_assessment_record_empty_inputs():
    """
    Even if an assessment has completely empty inputs, patient_summary must be a valid dict,
    not None, so client summary rendering (summary[k]) never raises TypeError.
    """
    raw_empty = {
        "id": "asm_empty_test",
        "inputs": None,
        "disease_results": None,
    }
    
    normalized = normalize_assessment_record(raw_empty)
    assert isinstance(normalized["patient_summary"], dict)
    assert isinstance(normalized["results"], dict)
    assert isinstance(normalized["summary"], dict)
    assert isinstance(normalized["disclaimer"], str)


@pytest.mark.asyncio
async def test_assessment_isolation_no_crossover():
    """
    Verify that retrieving distinct assessments returns isolated records without data leakage.
    """
    asm1 = js.create_assessment(
        patient_id="pat_alpha",
        patient_email="patient.alpha@example.com",
        inputs={"age": 30, "sex": "male", "systolic_bp": 115},
        disease_results={"diabetes": {"prediction": {"label": "low", "percentage": 10.0}}}
    )
    asm2 = js.create_assessment(
        patient_id="pat_beta",
        patient_email="patient.beta@example.com",
        inputs={"age": 65, "sex": "female", "systolic_bp": 155},
        disease_results={"diabetes": {"prediction": {"label": "high", "percentage": 85.0}}}
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r1 = await ac.get(f"/api/assessments/{asm1['id']}")
        r2 = await ac.get(f"/api/assessments/{asm2['id']}")

        assert r1.status_code == 200
        assert r2.status_code == 200
        d1 = r1.json()
        d2 = r2.json()

        assert d1["patient_email"] == "patient.alpha@example.com"
        assert d1["patient_summary"]["age"] == 30
        assert d2["patient_email"] == "patient.beta@example.com"
        assert d2["patient_summary"]["age"] == 65
