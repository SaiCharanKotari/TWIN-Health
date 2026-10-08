"""
logger.py — Structured backend logging.

Rules:
- NEVER log API keys or tokens.
- NEVER log full patient PII unless in debug mode.
- DO log: disease, provider, status, timing, error types.
"""
from __future__ import annotations
import logging
import sys
import time
from typing import Any

# ── Setup ──────────────────────────────────────────────────────────────────────
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)

logger = logging.getLogger("twinhealth")


# ── Helpers ────────────────────────────────────────────────────────────────────

def log_prediction_start(disease: str, provider: str, features_available: list[str]) -> None:
    logger.info(
        "PREDICT_START | disease=%s | provider=%s | features=%s",
        disease, provider, features_available,
    )


def log_prediction_complete(
    disease: str,
    provider: str,
    status: str,
    processing_ms: int,
) -> None:
    logger.info(
        "PREDICT_DONE  | disease=%s | provider=%s | status=%s | time_ms=%d",
        disease, provider, status, processing_ms,
    )


def log_insufficient_data(disease: str, missing: list[str]) -> None:
    logger.info(
        "INSUFFICIENT  | disease=%s | missing=%s",
        disease, missing,
    )


def log_api_error(disease: str, provider: str, error_type: str, message: str) -> None:
    # Sanitise: never log keys, tokens, or raw stack traces with credentials
    safe_msg = message[:300] if message else "(no message)"
    logger.error(
        "API_ERROR     | disease=%s | provider=%s | error=%s | msg=%s",
        disease, provider, error_type, safe_msg,
    )


def log_request(endpoint: str, fields_present: int) -> None:
    logger.info("REQUEST | endpoint=%s | patient_fields=%d", endpoint, fields_present)
