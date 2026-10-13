"""adapters/diabetes.py — Type 2 Diabetes disease adapter."""
from __future__ import annotations
from typing import Any
from adapters.base import DiseaseAdapter
from models.registry import MODEL_REGISTRY
from schema import PatientData


class DiabetesAdapter(DiseaseAdapter):
    disease = "diabetes"

    def build_input(self, patient: PatientData, provider: Any = None) -> dict[str, Any]:
        """Extract diabetes-relevant fields without fabricating unmeasured clinical biomarkers."""
        if provider and provider.name == "local":
            # Extract glucose; HbA1c conversion only if glucose is unmeasured
            glucose_val = patient.fasting_glucose or patient.random_glucose
            if glucose_val is None and patient.hba1c:
                glucose_val = round(patient.hba1c * 28.7 - 46.7, 1)

            bp_val = patient.diastolic_bp
            bmi_val = patient.bmi or (
                round(patient.weight_kg / ((patient.height_cm / 100) ** 2), 1)
                if patient.height_cm and patient.weight_kg else None
            )
            pedigree_val = 0.65 if patient.family_history_diabetes else None
            pregnancies_val = 0 if patient.sex and str(patient.sex).lower() == "male" else None

            return {
                "pregnancies": pregnancies_val,
                "glucose": glucose_val,
                "blood_pressure": bp_val,
                "skin_thickness": None,
                "insulin": patient.insulin,
                "bmi": bmi_val,
                "diabetes_pedigree_function": pedigree_val,
                "age": patient.age,
            }

        p = patient.model_dump()
        fields = [
            "age", "sex", "bmi", "height_cm", "weight_kg",
            "fasting_glucose", "random_glucose", "hba1c", "insulin",
            "systolic_bp", "diastolic_bp",
            "smoking_status", "alcohol_use", "physical_activity",
            "hypertension", "diabetes_history",
            "family_history_diabetes",
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
