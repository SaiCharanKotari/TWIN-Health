"""
tests/test_local_models.py — Automated verification for local ML models and health checks.
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from schema import PatientData
from services.prediction_service import get_local_provider, run_detection
from models.registry import MODEL_REGISTRY


def test_local_model_artifacts_and_pipelines():
    """Verify that all 5 disease directories contain pipeline.joblib and metadata.json and load."""
    provider = get_local_provider()
    diseases = ["diabetes", "heart_disease", "ckd", "liver_disease", "stroke"]

    for d in diseases:
        assert d in provider.pipelines, f"Pipeline for {d} is not loaded"
        assert d in provider.metadata, f"Metadata for {d} is missing"
        assert hasattr(provider.pipelines[d], "predict_proba") or hasattr(provider.pipelines[d], "predict")


def test_local_provider_health_check():
    """Verify that health_check() runs test inferences successfully on all 5 disease pipelines."""
    provider = get_local_provider()
    health = provider.health_check()

    assert len(health) == 5
    for d, info in health.items():
        assert info["loaded"] is True, f"{d} pipeline failed to load"
        assert info["inference_test_passed"] is True, f"{d} inference test failed: {info.get('test_note')}"
        assert len(info["features"]) > 0
        assert info["error"] is None


@pytest.mark.asyncio
async def test_insufficient_data_produces_strict_insufficient_status():
    """Verify that missing mandatory features produces 'insufficient_data' and never fakes a prediction."""
    # Patient with only age and sex, no labs or blood pressure
    patient = PatientData(age=45, sex="male", height_cm=170, weight_kg=70)
    result = await run_detection(patient, provider_override="local")

    results = result["results"]

    # CKD requires creatinine or eGFR
    assert results["ckd"]["status"] == "insufficient_data"
    assert len(results["ckd"]["missing_features"]) > 0
    assert results["ckd"]["prediction"] is None

    # Heart disease requires systolic_bp and total_cholesterol
    assert results["heart_disease"]["status"] == "insufficient_data"
    assert results["heart_disease"]["prediction"] is None

    # Liver disease requires ALT or AST
    assert results["liver_disease"]["status"] == "insufficient_data"
    assert results["liver_disease"]["prediction"] is None


@pytest.mark.asyncio
async def test_sufficient_patient_inference_success():
    """Verify that a patient with full clinical markers executes real local inference with valid probabilities."""
    patient = PatientData(
        age=52,
        sex="male",
        height_cm=175,
        weight_kg=82,
        systolic_bp=140.0,
        diastolic_bp=88.0,
        heart_rate=75.0,
        fasting_glucose=115.0,
        total_cholesterol=210.0,
        creatinine=1.1,
        egfr=75.0,
        alt=35.0,
        ast=30.0
    )
    result = await run_detection(patient, provider_override="local")
    results = result["results"]

    for d in ["diabetes", "heart_disease", "ckd", "liver_disease", "stroke"]:
        res = results[d]
        assert res["status"] == "success", f"{d} failed with status {res.get('status')}: {res.get('error_message')}"
        assert res["prediction"] is not None
        prob = res["prediction"]["probability"]
        assert 0.01 <= prob <= 0.99
        assert res["prediction"]["label"] in ["low_risk", "moderate_risk", "high_risk"]
        assert res["model"]["provider"] == "local"
