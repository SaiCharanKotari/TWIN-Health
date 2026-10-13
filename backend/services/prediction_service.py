"""
services/prediction_service.py — Orchestrates all 5 disease predictions with strict sufficiency handling.
"""
from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from typing import Optional

from config import get_effective_provider
from models.registry import MODEL_REGISTRY
from schema import PatientData
from utils.logger import log_request

# ── Adapter registry ───────────────────────────────────────────────────────────
from adapters.diabetes      import DiabetesAdapter
from adapters.heart_disease import HeartDiseaseAdapter
from adapters.ckd           import CKDAdapter
from adapters.liver_disease import LiverDiseaseAdapter
from adapters.stroke        import StrokeAdapter

_ADAPTERS = {
    "diabetes":      DiabetesAdapter(),
    "heart_disease": HeartDiseaseAdapter(),
    "ckd":           CKDAdapter(),
    "liver_disease": LiverDiseaseAdapter(),
    "stroke":        StrokeAdapter(),
}

# ── Provider factory ───────────────────────────────────────────────────────────
_local_provider_instance = None
_mock_provider_instance = None


def get_local_provider():
    global _local_provider_instance
    if _local_provider_instance is None:
        from providers.local_provider import LocalProvider
        _local_provider_instance = LocalProvider()
    return _local_provider_instance


def _get_provider(disease: str, provider_override: Optional[str] = None):
    global _local_provider_instance, _mock_provider_instance
    chosen = provider_override or get_effective_provider(disease)

    if chosen == "local":
        return get_local_provider()

    if chosen == "mock":
        if _mock_provider_instance is None:
            from providers.mock_provider import MockProvider
            _mock_provider_instance = MockProvider()
        return _mock_provider_instance

    if chosen == "gemini":
        from providers.gemini_provider import GeminiProvider
        return GeminiProvider()

    if chosen == "huggingface":
        from providers.huggingface_provider import HuggingFaceProvider
        return HuggingFaceProvider()

    return get_local_provider()


# ── Main service ───────────────────────────────────────────────────────────────

async def run_detection(patient: PatientData, provider_override: Optional[str] = None) -> dict:
    """
    Run all enabled disease models against the patient data.
    Enforces that insufficient inputs return explicit insufficient_data status.
    """
    present = patient.present_fields()
    log_request("/api/detection/analyze", len(present))

    diseases_to_run: list[tuple[str, bool, list[str]]] = []

    # First pass: classify sufficiency strictly
    for disease, config in MODEL_REGISTRY.items():
        if not config.get("enabled", True):
            continue
        adapter = _ADAPTERS[disease]
        is_ok, missing = adapter.check_sufficiency(patient)
        diseases_to_run.append((disease, is_ok, missing))

    # Run predictions in parallel
    async def run_one(disease: str, is_ok: bool, missing: list[str]) -> tuple[str, dict]:
        adapter  = _ADAPTERS[disease]
        provider = _get_provider(disease, provider_override)
        result   = await adapter.predict(patient, provider, is_sufficient=is_ok, missing=missing)
        return disease, result

    tasks = [run_one(d, is_ok, missing) for (d, is_ok, missing) in diseases_to_run]
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    results: dict[str, dict] = {}
    for item in raw_results:
        if isinstance(item, Exception):
            continue
        disease, result = item
        results[disease] = result

    # Build response summary
    models_run          = len(diseases_to_run)
    models_success      = sum(1 for r in results.values() if r.get("status") == "success")
    models_insufficient = sum(1 for r in results.values() if r.get("status") == "insufficient_data")
    models_preliminary  = sum(1 for r in results.values() if r.get("status") == "preliminary")
    models_unavailable  = sum(1 for r in results.values() if r.get("status") == "model_unavailable")
    inference_errors    = sum(1 for r in results.values() if r.get("status") in ("api_error", "inference_error"))

    return {
        "patient_summary": patient.to_summary_dict(),
        "results": results,
        "summary": {
            "models_run":                 models_run,
            "models_success":             models_success,
            "models_insufficient":        models_insufficient,
            "models_preliminary":         models_preliminary,
            "models_unavailable":         models_unavailable,
            "inference_errors":           inference_errors,
            "timestamp":                  datetime.now(timezone.utc).isoformat(),
        },
        "disclaimer": (
            "This system is an academic AI-based risk prediction tool and is NOT a substitute "
            "for professional medical diagnosis or treatment."
        ),
    }
