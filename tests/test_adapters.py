"""
tests/test_adapters.py — Unit tests for disease adapters.

Tests: complete input, missing input, field mapping, BMI auto-compute.
Run with: cd backend && python -m pytest ../tests/test_adapters.py -v
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import pytest
from schema import PatientData
from adapters.diabetes      import DiabetesAdapter
from adapters.heart_disease import HeartDiseaseAdapter
from adapters.ckd           import CKDAdapter
from adapters.liver_disease import LiverDiseaseAdapter
from adapters.stroke        import StrokeAdapter


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_patient(**kwargs) -> PatientData:
    return PatientData(**kwargs)


# ── BMI auto-computation ──────────────────────────────────────────────────────

def test_bmi_auto_computed():
    p = make_patient(height_cm=170, weight_kg=70)
    assert p.bmi is not None
    assert abs(p.bmi - 24.22) < 0.1

def test_bmi_not_overridden_if_supplied():
    p = make_patient(height_cm=170, weight_kg=70, bmi=25.0)
    assert p.bmi == 25.0


# ── Diabetes adapter ──────────────────────────────────────────────────────────

class TestDiabetesAdapter:
    adapter = DiabetesAdapter()

    def test_sufficient_with_minimal_data(self):
        p = make_patient(age=45, sex='male', fasting_glucose=110, height_cm=170, weight_kg=70)
        ok, missing = self.adapter.check_sufficiency(p)
        assert ok, f"Expected sufficient. Missing: {missing}"
        assert missing == []

    def test_insufficient_no_glucose(self):
        p = make_patient(age=45, sex='male', height_cm=170, weight_kg=70)
        ok, missing = self.adapter.check_sufficiency(p)
        assert not ok
        assert any('glucose' in m.lower() or 'hba1c' in m.lower() for m in missing)

    def test_insufficient_no_age(self):
        p = make_patient(sex='female', fasting_glucose=120, height_cm=165, weight_kg=60)
        ok, missing = self.adapter.check_sufficiency(p)
        assert not ok
        assert 'age' in missing

    def test_hba1c_satisfies_glucose_requirement(self):
        p = make_patient(age=50, sex='female', hba1c=6.2, height_cm=160, weight_kg=65)
        ok, missing = self.adapter.check_sufficiency(p)
        assert ok

    def test_build_input_excludes_none_fields(self):
        p = make_patient(age=42, sex='male', fasting_glucose=105, height_cm=175, weight_kg=80)
        features = self.adapter.build_input(p)
        assert None not in features.values()
        assert 'age' in features
        assert 'fasting_glucose' in features
        # insulin is None — should NOT be in features
        assert 'insulin' not in features

    def test_missing_bmi_but_height_weight_present(self):
        p = make_patient(age=40, sex='male', fasting_glucose=100, height_cm=170, weight_kg=75)
        ok, _ = self.adapter.check_sufficiency(p)
        assert ok  # BMI auto-computed from height+weight

    def test_missing_all(self):
        p = make_patient()
        ok, missing = self.adapter.check_sufficiency(p)
        assert not ok
        assert len(missing) > 0


# ── Heart disease adapter ─────────────────────────────────────────────────────

class TestHeartDiseaseAdapter:
    adapter = HeartDiseaseAdapter()

    def test_sufficient_with_required_fields(self):
        p = make_patient(age=55, sex='male', systolic_bp=145, total_cholesterol=220)
        ok, missing = self.adapter.check_sufficiency(p)
        assert ok

    def test_insufficient_missing_bp(self):
        p = make_patient(age=55, sex='male', total_cholesterol=220)
        ok, missing = self.adapter.check_sufficiency(p)
        assert not ok
        assert 'systolic_bp' in missing

    def test_insufficient_missing_cholesterol(self):
        p = make_patient(age=55, sex='male', systolic_bp=145)
        ok, missing = self.adapter.check_sufficiency(p)
        assert not ok
        assert 'total_cholesterol' in missing


# ── CKD adapter ───────────────────────────────────────────────────────────────

class TestCKDAdapter:
    adapter = CKDAdapter()

    def test_sufficient_with_egfr(self):
        p = make_patient(age=50, sex='female', egfr=75)
        ok, missing = self.adapter.check_sufficiency(p)
        assert ok

    def test_sufficient_with_creatinine_only(self):
        p = make_patient(age=50, sex='female', creatinine=1.1)
        ok, missing = self.adapter.check_sufficiency(p)
        assert ok

    def test_insufficient_no_kidney_markers(self):
        """CKD MUST NOT run on only demographics — this is the critical test."""
        p = make_patient(age=60, sex='male', weight_kg=80, height_cm=175)
        ok, missing = self.adapter.check_sufficiency(p)
        assert not ok, "CKD should not run without eGFR or creatinine"

    def test_insufficient_empty_patient(self):
        p = make_patient()
        ok, _ = self.adapter.check_sufficiency(p)
        assert not ok


# ── Liver adapter ─────────────────────────────────────────────────────────────

class TestLiverAdapter:
    adapter = LiverDiseaseAdapter()

    def test_sufficient_with_alt(self):
        p = make_patient(age=40, alt=35)
        ok, _ = self.adapter.check_sufficiency(p)
        assert ok

    def test_sufficient_with_ast_only(self):
        p = make_patient(age=40, ast=40)
        ok, _ = self.adapter.check_sufficiency(p)
        assert ok

    def test_insufficient_no_liver_enzymes(self):
        p = make_patient(age=40, bmi=27.0)
        ok, missing = self.adapter.check_sufficiency(p)
        assert not ok


# ── Stroke adapter ────────────────────────────────────────────────────────────

class TestStrokeAdapter:
    adapter = StrokeAdapter()

    def test_sufficient_minimal(self):
        p = make_patient(age=65, sex='male', systolic_bp=160)
        ok, _ = self.adapter.check_sufficiency(p)
        assert ok

    def test_insufficient_no_bp(self):
        p = make_patient(age=65, sex='male')
        ok, missing = self.adapter.check_sufficiency(p)
        assert not ok
        assert 'systolic_bp' in missing
