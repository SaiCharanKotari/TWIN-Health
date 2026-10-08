"""adapters/ckd.py — Chronic Kidney Disease adapter."""
from __future__ import annotations
from typing import Any
from adapters.base import DiseaseAdapter
from models.registry import MODEL_REGISTRY
from schema import PatientData


class CKDAdapter(DiseaseAdapter):
    disease = "ckd"

    def build_input(self, patient: PatientData, provider: Any = None) -> dict[str, Any]:
        """Extract CKD-relevant fields. Only include non-None values."""
        if provider and provider.name == "local":
            su_val = 1 if patient.fasting_glucose and patient.fasting_glucose > 120 else 0
            bgr_val = patient.random_glucose or patient.fasting_glucose
            htn_val = 'yes' if patient.hypertension else 'no'
            dm_val = 'yes' if patient.diabetes_history else 'no'
            cad_val = 'yes' if patient.heart_disease_history else 'no'
            
            # Map urine protein / albumin
            al_val = 0
            if patient.urine_protein is not None:
                if patient.urine_protein > 300: al_val = 3
                elif patient.urine_protein > 100: al_val = 2
                elif patient.urine_protein > 30: al_val = 1
            elif patient.uacr is not None:
                if patient.uacr > 300: al_val = 3
                elif patient.uacr > 30: al_val = 1

            cr_val = patient.creatinine
            if cr_val is None and patient.egfr is not None:
                cr_val = round(max(0.6, 90.0 / max(1.0, patient.egfr)), 2)
            
            df_dict = {
                "age": patient.age,
                "bp": patient.systolic_bp,
                "sg": 1.020,
                "al": al_val,
                "su": su_val,
                "rbc": 'normal',
                "pc": 'normal',
                "pcc": 'notpresent',
                "ba": 'notpresent',
                "bgr": bgr_val,
                "bu": patient.bun,
                "sc": cr_val,
                "sod": patient.sodium,
                "pot": patient.potassium,
                "hemo": patient.hemoglobin,
                "pcv": patient.hematocrit,
                "wbcc": patient.wbc,
                "rbcc": None,
                "htn": htn_val,
                "dm": dm_val,
                "cad": cad_val,
                "appet": 'good',
                "pe": 'no',
                "ane": 'no',
            }
            return df_dict

        p = patient.model_dump()
        fields = [
            "age", "sex", "bmi",
            "systolic_bp", "diastolic_bp",
            "egfr", "creatinine", "bun",
            "urine_protein", "uacr",
            "fasting_glucose", "hba1c",
            "hypertension", "diabetes_history", "family_history_ckd",
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
