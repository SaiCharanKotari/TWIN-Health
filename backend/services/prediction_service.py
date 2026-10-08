"""
services/prediction_service.py — Orchestrates all 5 disease predictions.

Flow:
  1. For each disease in registry:
     a. Load adapter
     b. Check data sufficiency
     c. If sufficient → queue async prediction task
     d. If not → record insufficient_data result immediately
  2. Run all queued tasks in parallel (asyncio.gather)
  3. Aggregate and return all 5 results
"""
from __future__ import annotations
import asyncio
from datetime import datetime, timezone

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

def _get_provider(disease: str, provider_override: str = None):
    global _local_provider_instance, _mock_provider_instance
    chosen = provider_override or get_effective_provider(disease)

    if chosen == "local":
        if _local_provider_instance is None:
            from providers.local_provider import LocalProvider
            _local_provider_instance = LocalProvider()
        return _local_provider_instance

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

    # Fallback to local provider
    if _local_provider_instance is None:
        from providers.local_provider import LocalProvider
        _local_provider_instance = LocalProvider()
    return _local_provider_instance




# ── Main service ───────────────────────────────────────────────────────────────

async def run_detection(patient: PatientData, provider_override: str = None) -> dict:
    """
    Run all enabled disease models against the patient data.
    Returns the complete detection response.
    """
    present = patient.present_fields()
    log_request("/api/detection/analyze", len(present))

    diseases_to_run: list[tuple[str, bool, list[str]]] = []

    # First pass: classify sufficiency
    for disease, config in MODEL_REGISTRY.items():
        if not config.get("enabled", True):
            continue
        adapter = _ADAPTERS[disease]
        is_ok, missing = adapter.check_sufficiency(patient)
        diseases_to_run.append((disease, is_ok, missing))

    # Build parallel tasks for diseases with slight stagger to avoid API burst contention
    async def run_one(disease: str, is_ok: bool, missing: list[str], delay_sec: float = 0.0) -> tuple[str, dict]:
        if delay_sec > 0:
            await asyncio.sleep(delay_sec)
        adapter  = _ADAPTERS[disease]
        provider = _get_provider(disease, provider_override)
        result   = await adapter.predict(patient, provider, is_sufficient=is_ok, missing=missing)
        return disease, result

    tasks = [
        run_one(d, is_ok, missing, delay_sec=i * 0.15)
        for i, (d, is_ok, missing) in enumerate(diseases_to_run)
    ]
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    results: dict[str, dict] = {}

    # Collect predictions
    for item in raw_results:
        if isinstance(item, Exception):
            # Shouldn't happen (adapter.predict catches exceptions internally)
            continue
        disease, result = item
        results[disease] = result

    # Build response
    models_run     = len(diseases_to_run)
    models_preliminary = sum(1 for r in results.values() if r.get("status") == "preliminary")
    api_errors     = sum(1 for r in results.values() if r.get("status") == "api_error")

    return {
        "patient_summary": patient.to_summary_dict(),
        "results": results,
        "summary": {
            "models_run":                 models_run,
            "models_preliminary":         models_preliminary,
            "api_errors":                 api_errors,
            "timestamp":                  datetime.now(timezone.utc).isoformat(),
        },
        "disclaimer": (
            "This system is an academic AI-based prediction tool and is NOT a substitute "
            "for professional medical diagnosis or treatment."
        ),
    }
