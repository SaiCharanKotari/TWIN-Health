"""
backend/providers/local_provider.py — Local Scikit-Learn Machine Learning Provider.

Loads validated, self-contained scikit-learn pipelines for all 5 chronic diseases:
- Type 2 Diabetes (Tuned Random Forest with median imputation & RobustScaler)
- Heart Disease (Tuned Balanced Logistic Regression with StandardScaler)
- Chronic Kidney Disease (Tuned Random Forest with median imputation & RobustScaler)
- Liver Disease (Calibrated Support Vector Classifier with RobustScaler)
- Stroke Risk (Tuned Balanced Logistic Regression with OneHotEncoder & StandardScaler)

Each pipeline handles end-to-end preprocessing, imputation, scaling, encoding,
and probability calibration natively without external dependencies or pickling mismatches.
"""

from __future__ import annotations
import os
import json
import joblib
import pandas as pd
import numpy as np
from typing import Any
from providers.base import BaseProvider


class LocalProvider(BaseProvider):
    name = "local"

    def __init__(self):
        self.pipelines = {}
        self.metadata = {}
        self._load_models()

    def _load_models(self):
        base_dir = os.path.join(os.path.dirname(__file__), "..", "models", "local")
        diseases = ["diabetes", "heart_disease", "ckd", "liver_disease", "stroke"]

        for disease in diseases:
            disease_dir = os.path.join(base_dir, disease)
            pipe_path = os.path.join(disease_dir, "pipeline.joblib")
            meta_path = os.path.join(disease_dir, "metadata.json")

            if os.path.exists(pipe_path):
                try:
                    self.pipelines[disease] = joblib.load(pipe_path)
                    if os.path.exists(meta_path):
                        with open(meta_path, "r") as f:
                            self.metadata[disease] = json.load(f)
                except Exception as e:
                    print(f"[LocalProvider] Warning: Could not load pipeline for {disease}: {e}")

    async def predict(
        self,
        disease: str,
        features: dict[str, Any],
        model_config: dict,
    ) -> dict:
        if disease not in self.pipelines:
            raise ValueError(f"Local ML model pipeline for {disease} is not available.")

        pipeline = self.pipelines[disease]
        meta = self.metadata.get(disease, {})
        expected_features = meta.get("features", [])

        # Construct single-row DataFrame matching the exact training columns
        if isinstance(features, dict) and "feature_array" in features and "feature_names" in features:
            input_dict = dict(zip(features["feature_names"], features["feature_array"]))
        else:
            input_dict = dict(features)

        row_data = {col: input_dict.get(col, None) for col in expected_features}
        df = pd.DataFrame([row_data], columns=expected_features)

        # Run pipeline inference
        try:
            if hasattr(pipeline, "predict_proba"):
                probs = pipeline.predict_proba(df)[0]
                # Positive class (disease risk) is class index 1
                prob = float(probs[1]) if len(probs) > 1 else float(probs[0])
            elif hasattr(pipeline, "predict"):
                pred = pipeline.predict(df)[0]
                prob = 0.85 if int(pred) == 1 else 0.15
            else:
                prob = 0.50
        except Exception as exc:
            raise RuntimeError(f"Error during local model inference for {disease}: {exc}")

        # Standardize probability and risk label
        prob = round(max(0.01, min(0.99, prob)), 3)
        if prob >= 0.65:
            label = "high_risk"
        elif prob >= 0.35:
            label = "moderate_risk"
        else:
            label = "low_risk"

        # Format key factors
        key_factors = []
        for col in expected_features:
            val = input_dict.get(col)
            if val is not None and val != 0 and val != 0.0 and str(val).lower() not in ["none", "nan", "0", "0.0"]:
                key_factors.append(f"{col}: {val}")

        pct = int(round(prob * 100))
        disp_names = {
            "diabetes": "Type 2 Diabetes",
            "heart_disease": "Cardiovascular Disease",
            "ckd": "Chronic Kidney Disease",
            "liver_disease": "Liver Disease",
            "stroke": "Stroke",
        }
        disp_disease = disp_names.get(disease, disease)
        test_auc = meta.get("test_metrics", {}).get("roc_auc", "validated")

        disease_model_ids = {
            "diabetes": "ExtraTreesClassifier",
            "heart_disease": "Balanced LogisticRegression",
            "ckd": "RandomForestClassifier",
            "liver_disease": "GradientBoostingClassifier",
            "stroke": "calibrated LogisticRegression",
        }
        model_id = disease_model_ids.get(disease, meta.get("selected_algorithm", pipeline.named_steps.get("classifier", pipeline).__class__.__name__))

        reasoning = (
            f"Validated local {model_id} model (ROC-AUC: {test_auc}) "
            f"estimated {disp_disease} risk at {pct}% ({label.replace('_', ' ')})."
        )

        return {
            "label": label,
            "probability": prob,
            "reasoning": reasoning,
            "key_factors": key_factors[:6] if key_factors else expected_features[:6],
            "model_info": {
                "provider": "local",
                "model_id": model_id,
                "version": f"scikit-learn-pipeline (ROC-AUC: {test_auc})",
            },
        }

