"""adapters/heart_disease.py — Cardiovascular disease adapter."""
from __future__ import annotations
from typing import Any
from adapters.base import DiseaseAdapter
from models.registry import MODEL_REGISTRY
from schema import PatientData


class HeartDiseaseAdapter(DiseaseAdapter):
    disease = "heart_disease"

    def build_input(self, patient: PatientData, provider: Any = None) -> dict[str, Any]:
        """Extract heart disease fields using genuine clinical measurements."""
        if provider and provider.name == "local":
            sex_val = 1 if patient.sex and str(patient.sex).lower() == "male" else 0
            fbs_val = None
            if patient.fasting_glucose is not None:
                fbs_val = 1 if patient.fasting_glucose > 120 else 0

            return {
                "age": patient.age,
                "sex": sex_val,
                "cp": None,
                "trestbps": patient.systolic_bp,
                "chol": patient.total_cholesterol,
                "fbs": fbs_val,
                "restecg": None,
                "thalach": patient.heart_rate,
                "exang": None,
                "oldpeak": None,
                "slope": None,
                "ca": None,
                "thal": None,
            }

        p = patient.model_dump()
        fields = [
            "age", "sex", "bmi",
            "systolic_bp", "diastolic_bp",
            "total_cholesterol", "hdl", "ldl", "triglycerides",
            "fasting_glucose", "hba1c",
            "smoking_status", "physical_activity",
            "hypertension", "heart_disease_history", "family_history_heart_disease",
        ]
        return {k: p[k] for k in fields if p.get(k) is not None}

    def normalize_output(self, raw: dict, features_used: list[str], patient: PatientData = None) -> dict:
        config = MODEL_REGISTRY[self.disease]
        result = self._base_result(patient)
        completeness, avail, total = self._compute_completeness(patient, config) if patient else (0.0, 0, 0)
        p_dict = patient.model_dump() if patient else {}

        label = raw.get("label", "unknown")
        prob  = raw.get("probability")

        all_candidate_features = list(dict.fromkeys(
            config.get("required_features", []) +
            [item for sublist in config.get("required_any_of", []) for item in sublist] +
            config.get("preferred_features", [])
        ))
        provided_features = [f for f in all_candidate_features if p_dict.get(f) is not None]
        missing_optional  = [f for f in config.get("preferred_features", []) if p_dict.get(f) is None]

        result["prediction"] = {
            "label":       label,
            "probability": prob,
            "percentage":  int(round(prob * 100)) if prob is not None else None,
        }
        result["model"] = raw.get("model_info", {})
        result["input_summary"] = {
            "features_used":            features_used,
            "features_used_count":      len(features_used),
            "features_provided_values": {k: p_dict[k] for k in provided_features if p_dict.get(k) is not None},
            "required_features":        config.get("required_features", []),
            "required_any_of":          config.get("required_any_of", []),
            "preferred_features":       config.get("preferred_features", []),
            "missing_optional":         missing_optional,
            "data_completeness":        completeness,
            "total_required":           total,
            "available_required":       avail,
            "total_model_features":     len(all_candidate_features),
            "provided_model_features":  len(provided_features),
        }
        result["explanation"] = {
            "available": bool(raw.get("reasoning")),
            "text":      raw.get("reasoning"),
            "factors":   raw.get("key_factors", []),
        }
        return result
