"""
backend/routes/models.py — Real-time model registry health and audit endpoints.
"""
from __future__ import annotations
from fastapi import APIRouter
from services.prediction_service import get_local_provider
from models.registry import MODEL_REGISTRY

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("/health")
def get_models_health():
    """
    GET /api/models/health

    Inspects all 5 disease pipelines on disk:
    - Checks whether pipeline loads
    - Validates feature schema and dimensions
    - Executes live synthetic test inference
    - Reports algorithm type, training metrics (ROC-AUC), and errors if any
    """
    provider = get_local_provider()
    health_results = provider.health_check()

    all_ok = all(m["loaded"] and m["inference_test_passed"] for m in health_results.values())
    total_models = len(health_results)
    models_ready = sum(1 for m in health_results.values() if m["loaded"] and m["inference_test_passed"])

    return {
        "status": "healthy" if all_ok else "degraded",
        "models_ready": f"{models_ready}/{total_models}",
        "all_pipelines_operational": all_ok,
        "models": health_results,
        "registry_definition": MODEL_REGISTRY,
    }
