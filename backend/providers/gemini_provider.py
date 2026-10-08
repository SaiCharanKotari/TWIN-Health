"""
providers/gemini_provider.py — Google Gemini AI provider.

Each disease gets a focused prompt. Results are structured JSON.
Activated when GEMINI_API_KEY is valid and DEFAULT_PROVIDER=gemini.
"""
from __future__ import annotations
import asyncio
import json
import re
from typing import Any

import google.generativeai as genai

from config import GEMINI_API_KEY, GEMINI_MODEL
from providers.base import BaseProvider

# Configure once at import time
if GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here":
    genai.configure(api_key=GEMINI_API_KEY)

_DISEASE_SYSTEM_PROMPTS = {
    "diabetes": """You are a clinical AI assessing Type 2 Diabetes risk.
Use ADA criteria: fasting glucose ≥126 mg/dL or HbA1c ≥6.5% indicates diabetes; 100-125 or 5.7-6.4% is pre-diabetes.
If clinical blood tests are missing, provide a preliminary assessment based on age, BMI, and family/medical history.""",

    "heart_disease": """You are a clinical AI assessing cardiovascular disease risk.
Use Framingham-style factors: age, sex, BP, total cholesterol, HDL, smoking, diabetes.
If clinical data like BP or cholesterol are missing, provide a preliminary assessment based on available demographics and lifestyle factors.""",

    "ckd": """You are a clinical AI assessing Chronic Kidney Disease using KDIGO guidelines.
eGFR <60 for >3 months defines CKD. Stage by eGFR: G1≥90, G2 60-89, G3a 45-59, G3b 30-44, G4 15-29, G5<15.
If kidney function markers (eGFR/Creatinine) are missing, provide a preliminary risk assessment based on age, diabetes, and hypertension history.""",

    "liver_disease": """You are a clinical AI assessing liver disease risk.
Consider: ALT/AST ratio, enzyme elevation above ULN, alcohol use, BMI (NAFLD risk), bilirubin.
If liver enzymes are missing, provide a preliminary assessment based on BMI, alcohol use, and diabetes status.""",

    "stroke": """You are a clinical AI assessing stroke risk.
Key factors: age, hypertension (systolic BP), atrial fibrillation history, smoking, diabetes, prior stroke/TIA.
If BP or other clinical data is missing, provide a preliminary assessment based on available history and demographics.""",
}


class GeminiProvider(BaseProvider):
    name = "gemini"

    def __init__(self, model_name: str = None):
        self._MODEL_NAME = model_name or GEMINI_MODEL or "gemini-3.6-flash"

    def _get_model(self, disease: str, model_name: str = None):
        name = model_name or self._MODEL_NAME
        return genai.GenerativeModel(
            model_name=name,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.15,
                max_output_tokens=2048,
            ),
            system_instruction=self._build_system_prompt(disease),
        )

    def _build_system_prompt(self, disease: str) -> str:
        base = _DISEASE_SYSTEM_PROMPTS.get(disease, "You are a clinical risk assessment AI.")
        return base + """

Analyse the provided patient data and respond ONLY with this JSON (no markdown, no extra text):
{
  "label": "low_risk" | "moderate_risk" | "high_risk",
  "probability": <float 0.0-1.0 representing estimated disease risk severity>,
  "reasoning": "<1 short sentence of clinical reasoning referencing actual provided values>",
  "key_factors": ["<factor with value>", "<factor with value>"]
}

Calibration Rules:
- "low_risk": probability should be between 0.03 and 0.30
- "moderate_risk": probability should be between 0.31 and 0.65
- "high_risk": probability should be between 0.66 and 0.98
- Output valid JSON only. Keep reasoning concise.
- Use ONLY the provided data values. Do NOT invent values.
- Be medically conservative: when borderline, report moderate_risk.
"""

    def _build_patient_text(self, features: dict) -> str:
        lines = ["Patient data (only values explicitly available):"]
        for k, v in features.items():
            lines.append(f"  {k}: {v}")
        return "\n".join(lines)

    def _parse_response(self, text: str, disease: str) -> dict:
        text = text.strip()
        parsed = None

        # 1. Direct JSON parse
        try:
            parsed = json.loads(text)
        except Exception:
            pass

        # 2. Markdown code fences
        if parsed is None:
            m = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
            if m:
                try:
                    parsed = json.loads(m.group(1).strip())
                except Exception:
                    pass

        # 3. Outermost curly brackets
        if parsed is None:
            m = re.search(r"\{[\s\S]*\}", text)
            if m:
                try:
                    parsed = json.loads(m.group())
                except Exception:
                    pass

        # 4. Truncated JSON auto-repair (e.g. unclosed quotes or brackets)
        if parsed is None:
            brace_pos = text.find("{")
            if brace_pos != -1:
                candidate = text[brace_pos:]
                if candidate.count('"') % 2 != 0:
                    candidate += '"'
                if candidate.count("[") > candidate.count("]"):
                    candidate += "]"
                if candidate.count("{") > candidate.count("}"):
                    candidate += "}"
                try:
                    parsed = json.loads(candidate)
                except Exception:
                    pass

        # 5. Fallback regex extraction of key fields
        if parsed is None:
            parsed = {}
            lbl_m = re.search(r'"label"\s*:\s*"([a-zA-Z_]+)"', text)
            if lbl_m:
                parsed["label"] = lbl_m.group(1).lower()

            prob_m = re.search(r'"probability"\s*:\s*([0-9.]+)', text)
            if prob_m:
                try:
                    parsed["probability"] = float(prob_m.group(1))
                except ValueError:
                    pass

            reason_m = re.search(r'"reasoning"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"?', text)
            if reason_m:
                parsed["reasoning"] = reason_m.group(1).strip()

            factors_m = re.search(r'"key_factors"\s*:\s*\[(.*?)\]', text, re.DOTALL)
            if factors_m:
                parsed["key_factors"] = re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"', factors_m.group(1))

        if not parsed or ("label" not in parsed and "probability" not in parsed):
            raise ValueError(f"Cannot extract valid clinical risk from Gemini response for {disease}. Raw text: {text[:200]}")

        # Standardize & validate label
        label = parsed.get("label", "").lower()
        if label not in ("low_risk", "moderate_risk", "high_risk"):
            prob = parsed.get("probability")
            if prob is not None and isinstance(prob, (int, float)):
                if prob >= 0.65: label = "high_risk"
                elif prob >= 0.35: label = "moderate_risk"
                else: label = "low_risk"
            else:
                label = "moderate_risk"
        parsed["label"] = label

        # Calibrate probability
        prob = parsed.get("probability")
        if prob is not None:
            try:
                prob = float(prob)
                if not (0.0 <= prob <= 1.0):
                    prob = 0.80 if label == "high_risk" else (0.50 if label == "moderate_risk" else 0.15)
            except (ValueError, TypeError):
                prob = 0.80 if label == "high_risk" else (0.50 if label == "moderate_risk" else 0.15)
        else:
            prob = 0.80 if label == "high_risk" else (0.50 if label == "moderate_risk" else 0.15)
        parsed["probability"] = round(prob, 3)

        if not parsed.get("reasoning") or not isinstance(parsed.get("reasoning"), str):
            parsed["reasoning"] = "Clinical risk assessment completed based on provided laboratory and demographic indicators."

        if not isinstance(parsed.get("key_factors"), list):
            parsed["key_factors"] = []

        return parsed

    async def predict(
        self,
        disease: str,
        features: dict[str, Any],
        model_config: dict,
    ) -> dict:
        import asyncio
        import random
        
        model = self._get_model(disease)
        patient_text = self._build_patient_text(features)

        max_retries = 4
        raw = None
        last_exception = None

        for attempt in range(max_retries):
            try:
                response = await asyncio.to_thread(
                    model.generate_content, patient_text
                )
                if response and hasattr(response, 'text') and response.text:
                    raw = self._parse_response(response.text, disease)
                    break
                else:
                    raise ValueError("Empty response text from Gemini model")
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    # Exponential backoff with jitter
                    wait_time = (1.5 * (2 ** attempt)) + random.uniform(0.5, 1.5)
                    await asyncio.sleep(wait_time)
                    continue

        if raw is None:
            # Resilient fallback to deterministic clinical mock rather than crashing
            from providers.mock_provider import MockProvider
            fallback = MockProvider()
            raw = await fallback.predict(disease, features, model_config)
            raw["model_info"] = {
                "provider":  "gemini",
                "model_id":  self._MODEL_NAME,
                "version":   "fallback-recovered",
                "note":      f"Recovered via heuristic fallback after Gemini API latency/interruption: {last_exception}",
            }
            return raw

        return {
            "label":       raw.get("label", "unknown"),
            "probability": raw.get("probability"),
            "reasoning":   raw.get("reasoning"),
            "key_factors": raw.get("key_factors", []),
            "model_info": {
                "provider":  "gemini",
                "model_id":  self._MODEL_NAME,
                "version":   None,
            },
        }
