"""
providers/mock_provider.py — Mock provider for development and testing.

Returns deterministic, semi-realistic predictions based on the provided
patient features. Uses simple clinical heuristics — NOT real ML models.

Use DEFAULT_PROVIDER=mock in .env (or when no API key is set).
"""
from __future__ import annotations
import hashlib
import json
from typing import Any

from providers.base import BaseProvider


class MockProvider(BaseProvider):
    name = "mock"

    # Simple heuristic thresholds (clinical reference ranges)
    _THRESHOLDS = {
        "diabetes": {
            "fasting_glucose": [(126, 0.8), (100, 0.4), (0, 0.15)],  # ≥126 → 0.8, ≥100 → 0.4
            "hba1c":           [(6.5, 0.85), (5.7, 0.45), (0, 0.1)],
            "bmi":             [(30, 0.3), (25, 0.15), (0, 0.05)],
        },
        "heart_disease": {
            "systolic_bp":       [(160, 0.5), (140, 0.3), (0, 0.1)],
            "total_cholesterol": [(240, 0.45), (200, 0.2), (0, 0.05)],
        },
        "ckd": {
            "egfr":      [(0, 0.9), (30, 0.7), (60, 0.35), (90, 0.1)],  # LOWER is worse
            "creatinine": [(3.0, 0.85), (1.5, 0.45), (0, 0.1)],
        },
        "liver_disease": {
            "alt": [(80, 0.65), (40, 0.35), (0, 0.1)],
            "ast": [(80, 0.65), (40, 0.35), (0, 0.1)],
        },
        "stroke": {
            "systolic_bp": [(180, 0.65), (160, 0.45), (140, 0.25), (0, 0.1)],
        },
    }

    async def predict(
        self,
        disease: str,
        features: dict[str, Any],
        model_config: dict,
    ) -> dict:
        prob = self._estimate_probability(disease, features)
        label = self._prob_to_label(prob)

        # Deterministic reasoning based on features present
        reasoning = self._build_reasoning(disease, features, prob)
        key_factors = self._key_factors(disease, features)

        return {
            "label":       label,
            "probability": round(prob, 3),
            "reasoning":   reasoning,
            "key_factors": key_factors,
            "model_info": {
                "provider":   "mock",
                "model_id":   "mock-heuristic-v1",
                "version":    "1.0",
                "note":       "Development mock — replace with real model",
            },
        }

    # ── Internals ──────────────────────────────────────────────────────────────

    def _estimate_probability(self, disease: str, features: dict) -> float:
        thresholds = self._THRESHOLDS.get(disease, {})
        base = 0.08
        adjustments = []

        for field, levels in thresholds.items():
            val = features.get(field)
            if val is None:
                continue

            if field == "egfr":
                # eGFR: lower = higher risk
                added = False
                for threshold, contribution in sorted(levels, key=lambda x: x[0]):
                    if val <= threshold:
                        adjustments.append(contribution)
                        added = True
                        break
                if not added:
                    # eGFR >= 90 is normal/healthy
                    adjustments.append(0.02)
            else:
                # All others: higher = higher risk
                for threshold, contribution in sorted(levels, key=lambda x: -x[0]):
                    if val >= threshold:
                        adjustments.append(contribution)
                        break

        # Add lifestyle & history adjustments
        if features.get("smoking_status") == "current":
            adjustments.append(0.08)
        elif features.get("smoking_status") == "former":
            adjustments.append(0.03)

        if features.get("hypertension") is True:
            adjustments.append(0.08)
        if features.get("diabetes_history") is True and disease != "diabetes":
            adjustments.append(0.10)

        if disease in ("diabetes", "heart_disease"):
            fam = features.get("family_history_diabetes") or features.get("family_history_heart_disease")
            if fam:
                adjustments.append(0.05)

        age = features.get("age", 40)
        if age >= 65:
            adjustments.append(0.10)
        elif age >= 50:
            adjustments.append(0.05)

        prob = base + sum(adjustments)
        return min(0.97, max(0.03, prob))

    def _prob_to_label(self, prob: float) -> str:
        if prob >= 0.65:  return "high_risk"
        if prob >= 0.35:  return "moderate_risk"
        return "low_risk"

    def _build_reasoning(self, disease: str, features: dict, prob: float) -> str:
        pct = int(round(prob * 100))
        field_count = len(features)
        names = {
            "diabetes":      "diabetes",
            "heart_disease": "cardiovascular disease",
            "ckd":           "chronic kidney disease",
            "liver_disease": "liver disease",
            "stroke":        "stroke",
        }
        return (
            f"Based on {field_count} available data points, the estimated {names.get(disease, disease)} "
            f"risk is approximately {pct}%. "
            f"This is a development mock estimate using clinical reference thresholds. "
            f"Replace with a validated ML model for clinical use."
        )

    def _key_factors(self, disease: str, features: dict) -> list[str]:
        factors = []
        mapping = {
            "fasting_glucose": f"Fasting glucose: {features.get('fasting_glucose')} mg/dL",
            "hba1c":           f"HbA1c: {features.get('hba1c')}%",
            "systolic_bp":     f"Systolic BP: {features.get('systolic_bp')} mmHg",
            "total_cholesterol": f"Total cholesterol: {features.get('total_cholesterol')} mg/dL",
            "egfr":            f"eGFR: {features.get('egfr')} mL/min/1.73m²",
            "alt":             f"ALT: {features.get('alt')} U/L",
            "bmi":             f"BMI: {features.get('bmi')}",
            "age":             f"Age: {features.get('age')} years",
        }
        for k, label in mapping.items():
            if features.get(k) is not None:
                factors.append(label)
        return factors[:5]
