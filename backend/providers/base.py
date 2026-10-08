"""providers/base.py — Abstract provider interface."""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any


class BaseProvider(ABC):
    """
    Abstract model provider.

    Implementations:
      - GeminiProvider   (google-generativeai)
      - MockProvider     (dev/testing)
      - HuggingFaceProvider (skeleton for future HF models)
    """
    name: str  # e.g. "gemini", "mock", "huggingface"

    @abstractmethod
    async def predict(
        self,
        disease: str,
        features: dict[str, Any],
        model_config: dict,
    ) -> dict:
        """
        Send features to the model and return a raw response dict.

        The response must contain at minimum:
          - "label": str   (e.g. "high_risk", "positive", "1")
          - "probability": float | None
          - "reasoning": str | None
          - "key_factors": list[str]

        If the model doesn't return probability, set it to None.
        Never fabricate values.
        """
