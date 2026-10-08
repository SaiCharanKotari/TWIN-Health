"""
tests/test_detection_e2e.py — Comprehensive end-to-end tests for TwinHealth AI detection pipeline.
"""
import pytest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from schema import PatientData
from services.prediction_service import run_detection
from providers.mock_provider import MockProvider
from providers.local_provider import LocalProvider


@pytest.mark.asyncio
async def test_mock_detection_healthy_patient():
    """Verify that a healthy patient evaluated via MockProvider yields low risk scores."""
    p = PatientData(
        age=30,
        sex="female",
        height_cm=165,
        weight_kg=58,
        systolic_bp=115,
        diastolic_bp=75,
        fasting_glucose=88,
        total_cholesterol=170,
        hdl=55,
        ldl=95,
        egfr=105,
        creatinine=0.8,
        alt=20,
        ast=18
    )
    result = await run_detection(p, provider_override="mock")
    
    assert "results" in result
    assert result["summary"]["models_run"] == 5
    assert result["summary"]["models_preliminary"] == 0
    
    # Check that all 5 diseases are assessed as low risk
    for disease in ["diabetes", "heart_disease", "ckd", "liver_disease", "stroke"]:
        res = result["results"][disease]
        assert res["status"] == "success"
        assert res["prediction"]["label"] == "low_risk"
        assert res["prediction"]["percentage"] < 35


@pytest.mark.asyncio
async def test_mock_detection_high_risk_patient():
    """Verify that a high-risk patient yields elevated risk scores across diseases."""
    p = PatientData(
        age=68,
        sex="male",
        height_cm=175,
        weight_kg=98,
        systolic_bp=165,
        diastolic_bp=100,
        fasting_glucose=160,
        hba1c=8.2,
        total_cholesterol=260,
        hdl=32,
        ldl=180,
        egfr=28,
        creatinine=2.8,
        alt=95,
        ast=90,
        smoking_status="current",
        hypertension=True,
        diabetes_history=True
    )
    result = await run_detection(p, provider_override="mock")
    
    # Diabetes, CKD, and Heart disease should flag high risk
    assert result["results"]["diabetes"]["prediction"]["label"] == "high_risk"
    assert result["results"]["heart_disease"]["prediction"]["label"] == "high_risk"
    assert result["results"]["ckd"]["prediction"]["label"] == "high_risk"


@pytest.mark.asyncio
async def test_local_provider_healthy_patient():
    """Verify that local ML models produce low risk (and NOT inverted risk) for healthy patient."""
    p = PatientData(
        age=28,
        sex="female",
        height_cm=165,
        weight_kg=56,
        systolic_bp=112,
        diastolic_bp=72,
        fasting_glucose=85,
        hba1c=5.1,
        total_cholesterol=165,
        hdl=58,
        ldl=90,
        triglycerides=95,
        egfr=110,
        creatinine=0.7,
        bun=12.0,
        alt=18.0,
        ast=16.0,
        total_bilirubin=0.7,
        alp=65.0
    )
    result = await run_detection(p, provider_override="local")
    
    assert "results" in result
    for d in ["diabetes", "heart_disease", "stroke"]:
        res = result["results"][d]
        assert res["status"] == "success"
        # Must be low risk for healthy young female
        assert res["prediction"]["label"] == "low_risk"
        assert res["prediction"]["probability"] < 0.40


@pytest.mark.asyncio
async def test_local_provider_diabetic_patient():
    """Verify local ML model flags elevated risk for diabetic profile."""
    p = PatientData(
        age=58,
        sex="male",
        height_cm=172,
        weight_kg=92,
        fasting_glucose=180,
        hba1c=8.5,
        total_cholesterol=240,
        triglycerides=250,
        hdl=35,
        ldl=155,
        bun=24.0,
        creatinine=1.4
    )
    result = await run_detection(p, provider_override="local")
    diabetes_res = result["results"]["diabetes"]
    assert diabetes_res["prediction"]["label"] in ["high_risk", "moderate_risk"]
    assert diabetes_res["prediction"]["probability"] >= 0.50


@pytest.mark.asyncio
async def test_preliminary_mode_on_missing_clinical_data():
    """Verify that when only demographic data is provided, status is marked preliminary."""
    p = PatientData(
        age=45,
        sex="male",
        height_cm=175,
        weight_kg=80
        # No blood tests, no BP
    )
    result = await run_detection(p, provider_override="mock")
    
    # Heart disease and CKD require clinical labs/BP for full sufficiency
    assert result["summary"]["models_preliminary"] > 0
    assert result["results"]["ckd"]["status"] == "preliminary"
    assert len(result["results"]["ckd"]["missing_features"]) > 0


@pytest.mark.asyncio
async def test_api_health_endpoint():
    """Verify FastAPI /health endpoint."""
    from httpx import AsyncClient, ASGITransport
    from main import app
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert "default_provider" in data


@pytest.mark.asyncio
async def test_api_template_endpoints():
    """Verify template download endpoints."""
    from httpx import AsyncClient, ASGITransport
    from main import app
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res_b = await client.get("/api/detection/template/basic")
        assert res_b.status_code == 200
        assert "text/csv" in res_b.headers["content-type"]

        res_a = await client.get("/api/detection/template/advanced")
        assert res_a.status_code == 200
        assert "text/csv" in res_a.headers["content-type"]


@pytest.mark.asyncio
async def test_api_analyze_sample_patient():
    """Verify /api/detection/analyze with sample patient data."""
    from httpx import AsyncClient, ASGITransport
    from main import app
    
    payload = {
        "age": 47,
        "sex": "male",
        "height_cm": 172.5,
        "weight_kg": 84.5,
        "systolic_bp": 138,
        "diastolic_bp": 88,
        "fasting_glucose": 108,
        "hba1c": 5.9,
        "total_cholesterol": 212,
        "hdl": 44,
        "ldl": 133,
        "triglycerides": 176,
        "creatinine": 1.0,
        "egfr": 95.0,
        "alt": 36.0,
        "ast": 28.0
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/api/detection/analyze?provider=local", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["summary"]["models_run"] == 5
        assert "diabetes" in data["results"]
        assert "heart_disease" in data["results"]
        assert "ckd" in data["results"]
        assert "liver_disease" in data["results"]
        assert "stroke" in data["results"]

        # Verify exact local model IDs and provider
        expected_models = {
            "diabetes": "ExtraTreesClassifier",
            "heart_disease": "Balanced LogisticRegression",
            "ckd": "RandomForestClassifier",
            "liver_disease": "GradientBoostingClassifier",
            "stroke": "calibrated LogisticRegression",
        }
        for d, expected_id in expected_models.items():
            r = data["results"][d]
            assert r["status"] == "success"
            assert r["model"]["provider"] == "local", f"{d} did not use local provider!"
            assert r["model"]["model_id"] == expected_id, f"{d} model_id mismatch: {r['model']['model_id']}"
            assert r["model"].get("version") != "fallback-recovered"


@pytest.mark.asyncio
async def test_api_analyze_default_provider_is_local():
    """Verify /api/detection/analyze defaults to local provider without query param."""
    from httpx import AsyncClient, ASGITransport
    from main import app
    
    payload = {
        "age": 52,
        "sex": "female",
        "systolic_bp": 130,
        "fasting_glucose": 115,
        "total_cholesterol": 210,
        "creatinine": 1.1,
        "alt": 25.0,
        "ast": 22.0
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/api/detection/analyze", json=payload)
        assert res.status_code == 200
        data = res.json()
        for disease, res_dict in data["results"].items():
            if res_dict["status"] in ("success", "preliminary"):
                assert res_dict["model"]["provider"] == "local"
                assert res_dict["model"].get("version") != "fallback-recovered"


