"""adapters/stroke.py — Stroke risk adapter."""
from __future__ import annotations
from typing import Any
from adapters.base import DiseaseAdapter
from models.registry import MODEL_REGISTRY
from schema import PatientData


class StrokeAdapter(DiseaseAdapter):
    disease = "stroke"

    def build_input(self, patient: PatientData, provider: Any = None) -> dict[str, Any]:
        """Extract stroke risk factors without hardcoding demographic assumptions."""
        if provider and provider.name == "local":
            gender_val = None
            if patient.sex:
                gender_val = "Male" if str(patient.sex).lower() == "male" else "Female"

            htn_val = None
            if patient.hypertension is not None:
                htn_val = 1 if patient.hypertension else 0
            elif patient.systolic_bp is not None:
                htn_val = 1 if patient.systolic_bp >= 140 else 0

            hd_val = None
            if patient.heart_disease_history is not None:
                hd_val = 1 if patient.heart_disease_history else 0

            glucose_val = patient.fasting_glucose or patient.random_glucose
            if glucose_val is None and patient.hba1c:
                glucose_val = round(patient.hba1c * 28.7 - 46.7, 1)

            bmi_val = patient.bmi or (
                round(patient.weight_kg / ((patient.height_cm / 100) ** 2), 1)
                if patient.height_cm and patient.weight_kg else None
            )

            smoke_val = None
            if patient.smoking_status == "current":
                smoke_val = "smokes"
            elif patient.smoking_status == "former":
                smoke_val = "formerly smoked"
            elif patient.smoking_status == "never":
                smoke_val = "never smoked"
            elif patient.smoking_status:
                smoke_val = str(patient.smoking_status)

            return {
                "gender": gender_val,
                "age": patient.age,
                "hypertension": htn_val,
                "heart_disease": hd_val,
                "ever_married": None,
                "work_type": None,
                "residence_type": None,
                "avg_glucose_level": glucose_val,
                "bmi": bmi_val,
                "smoking_status": smoke_val,
            }

        p = patient.model_dump()
        fields = [
            "age", "sex", "bmi",
            "systolic_bp", "diastolic_bp", "heart_rate",
            "total_cholesterol", "hdl", "ldl",
            "smoking_status", "alcohol_use", "physical_activity",
            "hypertension", "diabetes_history",
            "heart_disease_history", "previous_stroke",
            "family_history_stroke", "family_history_heart_disease",
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
