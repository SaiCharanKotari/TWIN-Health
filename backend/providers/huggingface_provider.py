"""
providers/huggingface_provider.py — HuggingFace Inference API provider skeleton.

Activated per-disease when HF_<DISEASE>_MODEL env var is set.
Fill in the payload format when you have the actual HuggingFace model IDs.
"""
from __future__ import annotations
import asyncio
from typing import Any

import httpx

from config import HF_API_KEY, HF_MODEL_IDS, API_TIMEOUT_SECONDS
from providers.base import BaseProvider

HF_INFERENCE_URL = "https://api-inference.huggingface.co/models/{model_id}"


class HuggingFaceProvider(BaseProvider):
    name = "huggingface"

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {HF_API_KEY}",
            "Content-Type": "application/json",
        }

    def _build_payload(self, disease: str, features: dict) -> dict:
        """
        Build the exact request body for the HuggingFace model.

        IMPORTANT: Different models expect different payload formats.
        Update this method per-disease when you have the actual model IDs
        and know their expected input format.

        Current implementation: sends features as `inputs` dict.
        Adjust `feature_mapping` in registry.py to rename fields.
        """
        # Apply feature_mapping from registry (universal → model-specific names)
        from models.registry import MODEL_REGISTRY
        mapping = MODEL_REGISTRY.get(disease, {}).get("feature_mapping", {})
        mapped = {mapping.get(k, k): v for k, v in features.items()}
        return {"inputs": mapped}

    def _normalize_raw_response(self, raw: Any, disease: str) -> dict:
        """
        Normalise the many possible HuggingFace response formats.
        See spec section 9: Handle Different Model Outputs.
        """
        # Format A: raw class string/int e.g. "1" or 1
        if isinstance(raw, (str, int)):
            label_map = {"1": "positive", "0": "negative", 1: "positive", 0: "negative"}
            return {
                "label":       label_map.get(raw, str(raw)),
                "probability": None,
                "reasoning":   None,
                "key_factors": [],
            }

        # Format B: list of {label, score}
        if isinstance(raw, list) and raw and isinstance(raw[0], dict) and "score" in raw[0]:
            best = max(raw, key=lambda x: x["score"])
            return {
                "label":       best.get("label", "unknown"),
                "probability": round(best["score"], 4),
                "reasoning":   None,
                "key_factors": [],
            }

        # Format C: single {label, score}
        if isinstance(raw, dict) and "score" in raw:
            return {
                "label":       raw.get("label", "unknown"),
                "probability": round(raw["score"], 4),
                "reasoning":   None,
                "key_factors": [],
            }

        # Format D: unexpected — don't crash, return unknown
        return {
            "label":       "unknown",
            "probability": None,
            "reasoning":   f"Unexpected model output format: {str(raw)[:100]}",
            "key_factors": [],
        }

    async def predict(
        self,
        disease: str,
        features: dict[str, Any],
        model_config: dict,
    ) -> dict:
        model_id = HF_MODEL_IDS.get(disease, "")
        if not model_id:
            raise ValueError(
                f"No HuggingFace model ID configured for disease '{disease}'. "
                f"Set HF_{disease.upper()}_MODEL in your .env file."
            )

        url     = HF_INFERENCE_URL.format(model_id=model_id)
        payload = self._build_payload(disease, features)
        headers = self._get_headers()

        async with httpx.AsyncClient(timeout=API_TIMEOUT_SECONDS) as client:
            for attempt in range(1, 3):  # 2 attempts
                try:
                    resp = await client.post(url, json=payload, headers=headers)

                    if resp.status_code == 401:
                        raise PermissionError("HuggingFace API key invalid or expired.")
                    if resp.status_code == 429:
                        raise RuntimeError("HuggingFace rate limit reached.")
                    if resp.status_code == 503:
                        # Model loading — retry once after 5s
                        if attempt < 2:
                            await asyncio.sleep(5)
                            continue
                        raise RuntimeError("HuggingFace model is still loading. Try again in a moment.")

                    resp.raise_for_status()
                    raw = resp.json()
                    normalized = self._normalize_raw_response(raw, disease)
                    normalized["model_info"] = {
                        "provider":  "huggingface",
                        "model_id":  model_id,
                        "version":   resp.headers.get("x-model-sha", None),
                    }
                    return normalized

                except (httpx.TimeoutException, httpx.NetworkError) as e:
                    if attempt == 2:
                        raise RuntimeError(f"Network error reaching HuggingFace API: {e}") from e
                    await asyncio.sleep(2)
