"""
schema.py — Universal Patient Data model.

All fields are Optional. BMI is auto-derived from height + weight.
Field names follow the universal schema — never changed for a specific model.
Model-specific field mapping is handled in adapters.
"""
from __future__ import annotations
from pydantic import BaseModel, model_validator, Field
from typing import Optional, Literal


class PatientData(BaseModel):
    """
    Universal patient schema. Every field is Optional (null = not available).
    NEVER add fake defaults. NEVER substitute average values for None.
    """

    # ── Demographics ───────────────────────────────────────────────────────────
    age:       Optional[int]   = Field(None, ge=0, le=130, description="Age in years")
    sex:       Optional[Literal["male", "female", "other", "unknown"]] = None
    height_cm: Optional[float] = Field(None, gt=0, le=300, description="Height in cm")
    weight_kg: Optional[float] = Field(None, gt=0, le=700, description="Weight in kg")
    bmi:       Optional[float] = Field(None, gt=0, le=200, description="Auto-computed from height+weight")

    # ── Vitals ────────────────────────────────────────────────────────────────
    systolic_bp:  Optional[float] = Field(None, description="Systolic blood pressure (mmHg)")
    diastolic_bp: Optional[float] = Field(None, description="Diastolic blood pressure (mmHg)")
    heart_rate:   Optional[float] = Field(None, description="Resting heart rate (bpm)")

    # ── Blood sugar ────────────────────────────────────────────────────────────
    fasting_glucose: Optional[float] = Field(None, description="Fasting blood glucose (mg/dL)")
    random_glucose:  Optional[float] = Field(None, description="Random blood glucose (mg/dL)")
    hba1c:           Optional[float] = Field(None, description="Glycated haemoglobin (%)")
    insulin:         Optional[float] = Field(None, description="Serum insulin (μU/mL)")

    # ── Lipid panel ────────────────────────────────────────────────────────────
    total_cholesterol: Optional[float] = Field(None, description="Total cholesterol (mg/dL)")
    hdl:               Optional[float] = Field(None, description="HDL cholesterol (mg/dL)")
    ldl:               Optional[float] = Field(None, description="LDL cholesterol (mg/dL)")
    triglycerides:     Optional[float] = Field(None, description="Triglycerides (mg/dL)")

    # ── Kidney function ────────────────────────────────────────────────────────
    creatinine:    Optional[float] = Field(None, description="Serum creatinine (mg/dL)")
    egfr:          Optional[float] = Field(None, description="eGFR (mL/min/1.73m²)")
    bun:           Optional[float] = Field(None, description="Blood urea nitrogen (mg/dL)")
    uacr:          Optional[float] = Field(None, description="Urine albumin-to-creatinine ratio (mg/g)")
    urine_protein: Optional[float] = Field(None, description="Urine protein (mg/dL)")
    sodium:        Optional[float] = Field(None, description="Serum sodium (mEq/L)")
    potassium:     Optional[float] = Field(None, description="Serum potassium (mEq/L)")

    # ── Liver function ─────────────────────────────────────────────────────────
    alt:              Optional[float] = Field(None, description="Alanine aminotransferase (U/L)")
    ast:              Optional[float] = Field(None, description="Aspartate aminotransferase (U/L)")
    alp:              Optional[float] = Field(None, description="Alkaline phosphatase (U/L)")
    total_bilirubin:  Optional[float] = Field(None, description="Total bilirubin (mg/dL)")
    direct_bilirubin: Optional[float] = Field(None, description="Direct bilirubin (mg/dL)")
    albumin:          Optional[float] = Field(None, description="Serum albumin (g/dL)")
    total_protein:    Optional[float] = Field(None, description="Total serum protein (g/dL)")

    # ── Complete blood count ───────────────────────────────────────────────────
    hemoglobin: Optional[float] = Field(None, description="Hemoglobin (g/dL)")
    hematocrit: Optional[float] = Field(None, description="Hematocrit (%)")
    wbc:        Optional[float] = Field(None, description="White blood cell count (10³/µL)")

    # ── Lifestyle ──────────────────────────────────────────────────────────────
    smoking_status:    Optional[Literal["never", "former", "current", "unknown"]] = None
    alcohol_use:       Optional[Literal["none", "occasional", "regular", "unknown"]] = None
    physical_activity: Optional[Literal["low", "moderate", "high", "unknown"]] = None

    # ── Medical history ────────────────────────────────────────────────────────
    hypertension:          Optional[bool] = None
    diabetes_history:      Optional[bool] = None
    heart_disease_history: Optional[bool] = None
    kidney_disease_history: Optional[bool] = None
    liver_disease_history: Optional[bool] = None
    previous_stroke:       Optional[bool] = None

    # ── Family history ─────────────────────────────────────────────────────────
    family_history_diabetes:      Optional[bool] = None
    family_history_heart_disease: Optional[bool] = None
    family_history_kidney_disease: Optional[bool] = None
    family_history_liver_disease: Optional[bool] = None
    family_history_stroke:        Optional[bool] = None

    # ─────────────────────────────────────────────────────────────────────────
    @model_validator(mode="after")
    def _compute_bmi(self) -> "PatientData":
        """Auto-derive BMI from height + weight when the user didn't supply it."""
        if self.bmi is None and self.height_cm and self.weight_kg:
            h_m = self.height_cm / 100.0
            self.bmi = round(self.weight_kg / (h_m ** 2), 2)
        return self

    def present_fields(self) -> list[str]:
        """Return list of field names that are NOT None."""
        return [k for k, v in self.model_dump().items() if v is not None]

    def to_summary_dict(self) -> dict:
        """Return a clean dict of non-None fields for the patient summary."""
        return {k: v for k, v in self.model_dump().items() if v is not None}
