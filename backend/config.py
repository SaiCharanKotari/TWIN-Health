"""
config.py — Central configuration from environment variables.

All env vars live here. Import `config` anywhere in the backend.
"""
from __future__ import annotations
import os
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ───────────────────────────────────────────────────────────────────
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: str   = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
HF_API_KEY: str     = os.getenv("HF_API_KEY", "")

# ── Provider selection ─────────────────────────────────────────────────────────
# Options: "local" | "mock" | "gemini" | "huggingface"
DEFAULT_PROVIDER: str = os.getenv("DEFAULT_PROVIDER", "local")

# ── HuggingFace per-disease model IDs ─────────────────────────────────────────
HF_DIABETES_MODEL:      str = os.getenv("HF_DIABETES_MODEL", "")
HF_HEART_MODEL:         str = os.getenv("HF_HEART_MODEL", "")
HF_CKD_MODEL:           str = os.getenv("HF_CKD_MODEL", "")
HF_LIVER_MODEL:         str = os.getenv("HF_LIVER_MODEL", "")
HF_STROKE_MODEL:        str = os.getenv("HF_STROKE_MODEL", "")

# ── Request settings ───────────────────────────────────────────────────────────
API_TIMEOUT_SECONDS: int = int(os.getenv("API_TIMEOUT_SECONDS", "30"))
API_RETRY_ATTEMPTS:  int = int(os.getenv("API_RETRY_ATTEMPTS", "2"))

HF_MODEL_IDS: dict[str, str] = {
    "diabetes":      HF_DIABETES_MODEL,
    "heart_disease": HF_HEART_MODEL,
    "ckd":           HF_CKD_MODEL,
    "liver_disease": HF_LIVER_MODEL,
    "stroke":        HF_STROKE_MODEL,
}


def _gemini_key_valid() -> bool:
    return bool(GEMINI_API_KEY) and GEMINI_API_KEY != "your_gemini_api_key_here"


def _hf_key_valid() -> bool:
    return bool(HF_API_KEY) and HF_API_KEY != "your_hf_api_key_here"


def get_effective_provider(disease: str) -> str:
    """
    Resolve which provider will actually run for a given disease.

    Priority:
      1. If DEFAULT_PROVIDER=local          → local
      2. If DEFAULT_PROVIDER=mock           → mock
      3. If DEFAULT_PROVIDER=huggingface and HF model ID set for disease → huggingface
      4. If DEFAULT_PROVIDER=gemini and Gemini key valid → gemini
      5. Fallback → local (if models exist) or mock
    """
    if DEFAULT_PROVIDER == "local":
        return "local"

    if DEFAULT_PROVIDER == "mock":
        return "mock"

    if DEFAULT_PROVIDER == "huggingface":
        if _hf_key_valid() and HF_MODEL_IDS.get(disease):
            return "huggingface"

    if DEFAULT_PROVIDER == "gemini":
        if _gemini_key_valid():
            return "gemini"

    # Default provider is local ML
    return "local"

