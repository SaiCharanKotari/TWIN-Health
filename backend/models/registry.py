"""
registry.py — MODEL_REGISTRY: configuration-driven disease model definitions.

To add a new model: add/update an entry here.
To replace a model: change provider/model_id here.
Nothing else in the application needs to change.
"""
from __future__ import annotations

MODEL_REGISTRY: dict[str, dict] = {

    "diabetes": {
        "enabled": True,
        "display_name": "Type 2 Diabetes",
        "icon": "🩺",
        "description": "Estimates risk of developing Type 2 Diabetes",
        # Minimum fields — model WILL NOT run without all of these
        "required_features": [
            "age",
            "sex",
        ],
        # At least ONE of these glucose markers must be present
        "required_any_of": [
            ["fasting_glucose", "random_glucose", "hba1c"],
        ],
        # BMI or (height + weight) must be present
        "required_derived": ["bmi_or_weight_height"],
        # Extra fields that improve accuracy but are not mandatory
        "preferred_features": [
            "hba1c", "systolic_bp", "diastolic_bp",
            "physical_activity", "family_history_diabetes",
            "hypertension", "smoking_status",
        ],
    },

    "heart_disease": {
        "enabled": True,
        "display_name": "Heart Disease",
        "icon": "❤️",
        "description": "Estimates 10-year cardiovascular disease risk",
        "required_features": [
            "age", "sex", "systolic_bp", "total_cholesterol",
        ],
        "required_any_of": [],
        "required_derived": [],
        "preferred_features": [
            "diastolic_bp", "hdl", "ldl", "triglycerides",
            "heart_rate", "smoking_status", "hypertension",
            "diabetes_history", "family_history_heart_disease", "bmi",
        ],
    },

    "ckd": {
        "enabled": True,
        "display_name": "Chronic Kidney Disease",
        "icon": "🫘",
        "description": "Assesses CKD staging based on kidney function markers",
        "required_features": ["age", "sex"],
        # HARD REQUIREMENT: must have eGFR OR creatinine
        "required_any_of": [
            ["egfr", "creatinine"],
        ],
        "required_derived": [],
        "preferred_features": [
            "uacr", "urine_protein", "bun",
            "sodium", "potassium",
            "diabetes_history", "hypertension",
            "kidney_disease_history",
        ],
    },

    "liver_disease": {
        "enabled": True,
        "display_name": "Liver Disease",
        "icon": "🟤",
        "description": "Assesses liver stress and NAFLD/hepatic disease risk",
        "required_features": ["age"],
        # Must have at least one liver enzyme
        "required_any_of": [
            ["alt", "ast"],
        ],
        "required_derived": [],
        "preferred_features": [
            "alp", "total_bilirubin", "direct_bilirubin",
            "albumin", "total_protein",
            "bmi", "alcohol_use", "diabetes_history",
            "liver_disease_history",
        ],
    },

    "stroke": {
        "enabled": True,
        "display_name": "Stroke Risk",
        "icon": "🧠",
        "description": "Estimates stroke risk using cardiovascular and lifestyle factors",
        "required_features": ["age", "sex", "systolic_bp"],
        "required_any_of": [],
        "required_derived": [],
        "preferred_features": [
            "diastolic_bp", "smoking_status", "diabetes_history",
            "heart_disease_history", "total_cholesterol", "bmi",
            "physical_activity", "previous_stroke",
            "family_history_stroke", "hypertension",
        ],
    },
}
