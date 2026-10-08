"""
predictor.py — Gemini AI integration for disease risk assessment.

Sends the patient's available data to Gemini 1.5 Flash and receives a
structured JSON assessment for five disease models.  Only diseases with
sufficient clinical data are assessed; others get an "insufficient_data"
status explaining what is missing.
"""

from __future__ import annotations

import asyncio
import json
import os
import re

import google.generativeai as genai
from dotenv import load_dotenv

from config import GEMINI_API_KEY, GEMINI_MODEL
from schema import PatientData

load_dotenv()

_API_KEY = GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY", "")
if _API_KEY and _API_KEY != "your_gemini_api_key_here":
    genai.configure(api_key=_API_KEY)

# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are MediRisk, a clinical decision-support AI assistant.
Your job is to analyse patient data and return a structured disease risk assessment.

━━━ HARD RULES ━━━
1. Assess ONLY diseases for which you have the minimum required data (listed below).
2. NEVER fabricate, estimate, or interpolate missing laboratory values.
3. NEVER assess CKD without kidney-function data (eGFR or creatinine). This is non-negotiable.
4. Use evidence-based clinical criteria: ADA criteria for diabetes, Framingham for CVD, KDIGO for CKD, etc.
5. Be medically conservative — when borderline, err toward flagging and recommending evaluation.

━━━ MINIMUM DATA REQUIREMENTS ━━━
• Diabetes       : age AND (fasting_glucose OR hba1c) AND (bmi OR weight_kg)
• Heart Disease  : age AND sex AND systolic_bp AND total_cholesterol
• CKD            : egfr OR creatinine  ← HARD REQUIREMENT
• Liver Disease  : (alt OR ast) AND age
• Stroke         : age AND sex AND systolic_bp

━━━ RISK LEVELS ━━━
• low       : 0–25
• moderate  : 26–50
• high      : 51–75
• very_high : 76–100

━━━ OUTPUT FORMAT ━━━
Return ONLY a single JSON object — no markdown, no code fences, no extra text.

{
  "assessments": [
    {
      "disease": "diabetes",
      "display_name": "Type 2 Diabetes",
      "status": "assessed",
      "risk_level": "low|moderate|high|very_high",
      "risk_score": <integer 0-100>,
      "key_factors": ["<factor>", "<factor>", "<factor>"],
      "reasoning": "<2-3 sentences of clinical reasoning referencing the actual values provided>",
      "recommendation": "<specific, actionable recommendation>",
      "data_used": ["age", "fasting_glucose", "bmi"]
    },
    {
      "disease": "ckd",
      "display_name": "Chronic Kidney Disease",
      "status": "insufficient_data",
      "missing_fields": ["egfr", "creatinine", "uacr"],
      "message": "<explain why these markers are required and that early CKD has no symptoms>",
      "data_used": []
    }
  ],
  "overall_summary": "<2-3 sentence holistic health summary emphasising the most urgent findings>",
  "priority_actions": ["<action 1>", "<action 2>", "<action 3>"]
}

You MUST include an entry for ALL FIVE diseases:
  diabetes, heart_disease, ckd, liver_disease, stroke
"""

# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_patient_summary(patient: PatientData) -> str:
    data = patient.model_dump(exclude_none=True)
    lines = ["Patient data (only values explicitly provided are listed):"]
    for key, value in data.items():
        lines.append(f"  {key}: {value}")
    return "\n".join(lines)


def _parse_json_from_text(text: str) -> dict:
    """Best-effort extraction of a JSON object from raw model output."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Strip accidental markdown code fences
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # Last resort: find the outermost { … }
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        return json.loads(match.group())
    raise ValueError("Could not extract valid JSON from model response")


# ── Core prediction function ──────────────────────────────────────────────────

def _predict_sync(patient: PatientData) -> dict:
    """Synchronous Gemini call — runs in a thread via asyncio.to_thread."""
    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL or "gemini-3.6-flash",
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.15,
            max_output_tokens=2048,
        ),
        system_instruction=SYSTEM_PROMPT,
    )
    patient_text = _build_patient_summary(patient)
    response = model.generate_content(patient_text)
    return _parse_json_from_text(response.text)


async def predict(patient: PatientData) -> dict:
    """Async wrapper — keeps the FastAPI event loop unblocked."""
    return await asyncio.to_thread(_predict_sync, patient)
