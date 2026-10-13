"""
tests/test_patient_inputs.py
Comprehensive input testing for all PatientData fields and the 5 disease model pipelines.
Covers:
- Schema field validation: types, boundaries, enums, auto-derivation, optionality, zeroes, booleans.
- Frontend-backend parity: templates, email persistence, completeness.
- Five disease model coverage: sufficient, insufficient, missing optional, boundaries, exceptions.
"""
import os
import sys
import pytest
from pydantic import ValidationError
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
from main import app
from schema import PatientData
from adapters.diabetes      import DiabetesAdapter
from adapters.heart_disease import HeartDiseaseAdapter
from adapters.ckd           import CKDAdapter
from adapters.liver_disease import LiverDiseaseAdapter
from adapters.stroke        import StrokeAdapter
from services.prediction_service import run_detection
from storage import json_storage as js


# ═════════════════════════════════════════════════════════════════════════════
# 1. SCHEMA AND FIELD VALIDATION TESTS
# ═════════════════════════════════════════════════════════════════════════════

def test_patient_data_all_optional():
    """All fields must be optional; empty PatientData initializes without error."""
    p = PatientData()
    assert p.present_fields() == []
    assert p.to_summary_dict() == {}


@pytest.mark.parametrize("age_val, valid", [
    (0, True),
    (25, True),
    (130, True),
    (-1, False),
    (131, False),
    ("invalid_age", False),
])
def test_age_boundaries_and_types(age_val, valid):
    if valid:
        p = PatientData(age=age_val)
        assert p.age == age_val
    else:
        with pytest.raises(ValidationError):
            PatientData(age=age_val)


@pytest.mark.parametrize("sex_val, valid", [
    ("male", True),
    ("female", True),
    ("other", True),
    ("unknown", True),
    ("invalid_gender", False),
    (123, False),
])
def test_sex_enums(sex_val, valid):
    if valid:
        p = PatientData(sex=sex_val)
        assert p.sex == sex_val
    else:
        with pytest.raises(ValidationError):
            PatientData(sex=sex_val)


def test_height_weight_bmi_autoderivation():
    """BMI is auto-derived when height and weight are provided, but not overwritten if given."""
    p_auto = PatientData(height_cm=180.0, weight_kg=81.0)
    assert p_auto.bmi == 25.0

    p_explicit = PatientData(height_cm=180.0, weight_kg=81.0, bmi=29.2)
    assert p_explicit.bmi == 29.2


@pytest.mark.parametrize("height, weight, valid", [
    (170.0, 70.0, True),
    (0, 70.0, False),      # height must be gt=0
    (301.0, 70.0, False),  # height le=300
    (170.0, 0, False),     # weight gt=0
    (170.0, 750.0, False), # weight le=700
])
def test_height_weight_boundaries(height, weight, valid):
    if valid:
        p = PatientData(height_cm=height, weight_kg=weight)
        assert p.height_cm == height
    else:
        with pytest.raises(ValidationError):
            PatientData(height_cm=height, weight_kg=weight)


@pytest.mark.parametrize("field_name, valid_val, invalid_val", [
    ("systolic_bp", 120.5, "high"),
    ("diastolic_bp", 80.0, "normal"),
    ("heart_rate", 72.0, "fast"),
    ("fasting_glucose", 95.5, "sugar"),
    ("random_glucose", 140.0, "high"),
    ("hba1c", 5.7, "bad"),
    ("insulin", 12.4, "none"),
    ("total_cholesterol", 190.0, "elevated"),
    ("hdl", 55.0, "good"),
    ("ldl", 110.0, "bad"),
    ("triglycerides", 150.0, "normal"),
    ("creatinine", 0.9, "clear"),
    ("egfr", 95.0, "good"),
    ("bun", 15.0, "normal"),
    ("uacr", 25.0, "normal"),
    ("urine_protein", 0.0, "zero"),
    ("sodium", 140.0, "salt"),
    ("potassium", 4.2, "k"),
    ("alt", 25.0, "high"),
    ("ast", 22.0, "normal"),
    ("alp", 65.0, "ok"),
    ("total_bilirubin", 0.8, "normal"),
    ("direct_bilirubin", 0.2, "trace"),
    ("albumin", 4.5, "protein"),
    ("total_protein", 7.2, "ok"),
    ("hemoglobin", 14.5, "iron"),
    ("hematocrit", 42.0, "pct"),
    ("wbc", 6.5, "cells"),
])
def test_numeric_clinical_fields(field_name, valid_val, invalid_val):
    p = PatientData(**{field_name: valid_val})
    assert getattr(p, field_name) == valid_val

    with pytest.raises(ValidationError):
        PatientData(**{field_name: invalid_val})


@pytest.mark.parametrize("lifestyle_field, valid_values, invalid_val", [
    ("smoking_status", ["never", "former", "current", "unknown"], "daily"),
    ("alcohol_use", ["none", "occasional", "regular", "unknown"], "social"),
    ("physical_activity", ["low", "moderate", "high", "unknown"], "active"),
])
def test_lifestyle_enums(lifestyle_field, valid_values, invalid_val):
    for val in valid_values:
        p = PatientData(**{lifestyle_field: val})
        assert getattr(p, lifestyle_field) == val

    with pytest.raises(ValidationError):
        PatientData(**{lifestyle_field: invalid_val})


@pytest.mark.parametrize("bool_field", [
    "hypertension",
    "diabetes_history",
    "heart_disease_history",
    "kidney_disease_history",
    "liver_disease_history",
    "previous_stroke",
    "family_history_diabetes",
    "family_history_heart_disease",
    "family_history_kidney_disease",
    "family_history_liver_disease",
    "family_history_stroke",
])
def test_boolean_history_fields(bool_field):
    # Test True
    p_true = PatientData(**{bool_field: True})
    assert getattr(p_true, bool_field) is True

    # Test False (must not be dropped or converted to None)
    p_false = PatientData(**{bool_field: False})
    assert getattr(p_false, bool_field) is False

    # Test None
    p_none = PatientData(**{bool_field: None})
    assert getattr(p_none, bool_field) is None

    # Invalid non-boolean value
    with pytest.raises(ValidationError):
        PatientData(**{bool_field: "maybe_not_a_bool"})


# ═════════════════════════════════════════════════════════════════════════════
# 2. FIVE DISEASE MODEL ADAPTER & PIPELINE COVERAGE
# ═════════════════════════════════════════════════════════════════════════════

def test_diabetes_adapter_coverage():
    adapter = DiabetesAdapter()
    
    # 1. Sufficient
    p_suff = PatientData(age=50, sex="male", fasting_glucose=126.0, height_cm=170, weight_kg=70)
    ok, missing = adapter.check_sufficiency(p_suff)
    assert ok is True
    assert missing == []
    inp = adapter.build_input(p_suff)
    assert "fasting_glucose" in inp
    
    # 2. Missing glucose and hba1c
    p_no_gluc = PatientData(age=50, sex="male", height_cm=170, weight_kg=70)
    ok, missing = adapter.check_sufficiency(p_no_gluc)
    assert ok is False

    # 3. Missing age
    p_no_age = PatientData(sex="male", fasting_glucose=110.0, height_cm=170, weight_kg=70)
    ok, missing = adapter.check_sufficiency(p_no_age)
    assert ok is False
    assert "age" in missing

    # 4. HbA1c satisfies requirement in place of fasting_glucose
    p_hba1c = PatientData(age=50, sex="female", hba1c=6.8, height_cm=160, weight_kg=65)
    ok, missing = adapter.check_sufficiency(p_hba1c)
    assert ok is True


def test_heart_disease_adapter_coverage():
    adapter = HeartDiseaseAdapter()
    
    # 1. Sufficient
    p_suff = PatientData(age=55, sex="male", systolic_bp=140.0, total_cholesterol=220.0)
    ok, missing = adapter.check_sufficiency(p_suff)
    assert ok is True

    # 2. Missing BP
    p_no_bp = PatientData(age=55, sex="male", total_cholesterol=220.0)
    ok, missing = adapter.check_sufficiency(p_no_bp)
    assert ok is False

    # 3. Missing cholesterol
    p_no_chol = PatientData(age=55, sex="male", systolic_bp=140.0)
    ok, missing = adapter.check_sufficiency(p_no_chol)
    assert ok is False


def test_ckd_adapter_coverage():
    adapter = CKDAdapter()

    # 1. Sufficient with eGFR
    p_egfr = PatientData(age=60, sex="male", systolic_bp=120, egfr=45.0)
    ok, missing = adapter.check_sufficiency(p_egfr)
    assert ok is True

    # 2. Sufficient with creatinine
    p_creat = PatientData(age=60, sex="male", systolic_bp=120, creatinine=1.8)
    ok, missing = adapter.check_sufficiency(p_creat)
    assert ok is True

    # 3. Insufficient (no renal markers)
    p_none = PatientData(age=60, systolic_bp=130.0)
    ok, missing = adapter.check_sufficiency(p_none)
    assert ok is False


def test_liver_adapter_coverage():
    adapter = LiverDiseaseAdapter()

    # 1. Sufficient with ALT
    p_alt = PatientData(age=45, sex="female", alt=55.0, total_bilirubin=1.0)
    ok, missing = adapter.check_sufficiency(p_alt)
    assert ok is True

    # 2. Sufficient with AST
    p_ast = PatientData(age=45, sex="female", ast=60.0, total_bilirubin=1.0)
    ok, missing = adapter.check_sufficiency(p_ast)
    assert ok is True

    # 3. Insufficient without enzymes
    p_none = PatientData(age=45, sex="female", total_bilirubin=1.2)
    ok, missing = adapter.check_sufficiency(p_none)
    assert ok is False


def test_stroke_adapter_coverage():
    adapter = StrokeAdapter()

    # 1. Sufficient
    p_suff = PatientData(age=65, sex="male", systolic_bp=150.0, fasting_glucose=100)
    ok, missing = adapter.check_sufficiency(p_suff)
    assert ok is True

    # 2. Insufficient without BP
    p_no_bp = PatientData(age=65)
    ok, missing = adapter.check_sufficiency(p_no_bp)
    assert ok is False


@pytest.mark.asyncio
async def test_all_five_diseases_local_detection():
    """Verify local detection runs all 5 disease models safely on a full patient profile."""
    patient = PatientData(
        age=52,
        sex="male",
        height_cm=175.0,
        weight_kg=84.0,
        systolic_bp=138.0,
        diastolic_bp=88.0,
        heart_rate=76.0,
        fasting_glucose=118.0,
        hba1c=6.1,
        total_cholesterol=210.0,
        hdl=45.0,
        ldl=135.0,
        triglycerides=160.0,
        creatinine=1.1,
        egfr=80.0,
        alt=35.0,
        ast=30.0,
        smoking_status="former",
        hypertension=True,
    )

    detection = await run_detection(patient, provider_override="local")
    assert "results" in detection
    results = detection["results"]

    valid_labels = {"low", "moderate", "high", "critical", "unknown", "low_risk", "moderate_risk", "high_risk", "critical_risk"}

    for d in ["diabetes", "heart_disease", "ckd", "liver_disease", "stroke"]:
        assert d in results, f"Disease {d} missing in detection output"
        res = results[d]
        assert "status" in res
        # Must produce valid prediction object
        if res["status"] == "success":
            pred = res["prediction"]
            assert "percentage" in pred
            assert 0.0 <= pred["percentage"] <= 100.0
            assert pred["label"] in valid_labels


# ═════════════════════════════════════════════════════════════════════════════
# 3. FRONTEND-TO-BACKEND API INTEGRATION & TEMPLATES
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_template_download_endpoints():
    """Verify CSV/Excel templates are served correctly for basic and advanced modes."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r_basic = await ac.get("/api/detection/template/basic")
        assert r_basic.status_code == 200
        assert "text/csv" in r_basic.headers.get("content-type", "")

        r_adv = await ac.get("/api/detection/template/advanced")
        assert r_adv.status_code == 200
        assert "text/csv" in r_adv.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_detection_analyze_persists_email_and_assessment():
    """Test full /api/detection/analyze call persists patient email and creates assessment."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {
            "patient_email": "parity.patient@example.com",
            "patient_name": "Parity Patient",
            "age": 48,
            "sex": "female",
            "systolic_bp": 128,
            "fasting_glucose": 105,
            "total_cholesterol": 195,
            "creatinine": 0.9,
            "alt": 22,
        }
        res = await ac.post("/api/detection/analyze", json=payload)
        assert res.status_code == 200
        data = res.json()

        assert "assessment_id" in data
        assert data["patient_email"] == "parity.patient@example.com"
        assert "results" in data

        # Check retrieval of created assessment
        asm_res = await ac.get(f"/api/assessments/{data['assessment_id']}")
        assert asm_res.status_code == 200
        asm_data = asm_res.json()
        assert asm_data["patient_summary"]["age"] == 48
        assert asm_data["patient_summary"]["sex"] == "female"
