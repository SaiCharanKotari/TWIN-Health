"""adapters/heart_disease.py — Heart disease adapter."""
from __future__ import annotations
from typing import Any
from adapters.base import DiseaseAdapter
from models.registry import MODEL_REGISTRY
from schema import PatientData


class HeartDiseaseAdapter(DiseaseAdapter):
    disease = "heart_disease"

    def build_input(self, patient: PatientData, provider: Any = None) -> dict[str, Any]:
        """Extract heart-disease-relevant fields. Only include non-None values."""
        if provider and provider.name == "local":
            sex_val = 1 if patient.sex and str(patient.sex).lower() == 'male' else 0
            fbs_val = 1 if patient.fasting_glucose and patient.fasting_glucose > 120 else 0
            
            # Clinical mapping for Cleveland features
            has_hd = bool(patient.heart_disease_history)
            cp_val = 4 if has_hd else (2 if patient.hypertension else 3)
            restecg_val = 1 if (has_hd or (patient.systolic_bp and patient.systolic_bp >= 150)) else 0
            exang_val = 1 if has_hd else 0
            oldpeak_val = 1.8 if has_hd else 0.0
            slope_val = 2 if has_hd else 1
            
            df_dict = {
                "age": patient.age,
                "sex": sex_val,
                "cp": cp_val,
                "trestbps": patient.systolic_bp,
                "chol": patient.total_cholesterol,
                "fbs": fbs_val,
                "restecg": restecg_val,
                "thalach": patient.heart_rate or 145.0,
                "exang": exang_val,
                "oldpeak": oldpeak_val,
                "slope": slope_val,
                "ca": None,
                "thal": None,
            }
            return df_dict

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
        result = self._base_result()
        completeness, avail, total = self._compute_completeness(patient, config)
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
