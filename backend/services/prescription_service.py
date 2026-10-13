"""
backend/services/prescription_service.py — Doctor Prescription Receipt Ingestion & Medication Parser.

Safety Protocol:
- AI OCR/Vision extracts potential candidate medicines when available.
- When vision is unavailable or uncertain, requires explicit clinician verification.
- NEVER silently fabricates prescription medications or alters dosages autonomously.
"""
from __future__ import annotations
import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
import google.generativeai as genai

from config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger("twinhealth.prescription")


async def parse_prescription_receipt(
    file_bytes: bytes,
    filename: str,
    content_type: str
) -> Dict[str, Any]:
    """
    Parses an uploaded prescription receipt image or document.
    Enforces that medications require explicit clinician verification.
    """
    # 1. Attempt Gemini Vision Parsing if API Key available and non-empty file
    if GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here" and len(file_bytes) > 100:
        try:
            parsed = await asyncio.wait_for(
                _parse_with_gemini_vision(file_bytes, content_type),
                timeout=12.0
            )
            if parsed and isinstance(parsed, dict) and "medications" in parsed:
                parsed["source"] = "gemini-vision-ocr"
                parsed["requires_verification"] = True
                parsed["status"] = "extracted_pending_verification"
                return parsed
        except Exception as exc:
            logger.warning(f"Gemini prescription vision parsing unavailable/timed out: {exc}. Using clinical receipt slot.")

    # 2. Safe Fallback: Require clinician manual entry or verification
    return {
        "doctor_name": "Attending Physician / Clinic",
        "prescription_date": "Current Assessment",
        "filename": filename,
        "source": "manual_clinical_verification_required",
        "requires_verification": True,
        "status": "pending_doctor_entry",
        "medications": [],
        "clinical_notes": (
            f"Prescription receipt '{filename}' was uploaded. "
            "To ensure patient safety, medications must be confirmed and verified by the attending physician."
        )
    }


async def _parse_with_gemini_vision(file_bytes: bytes, content_type: str) -> Optional[Dict[str, Any]]:
    """Uses Gemini vision model to extract candidate text from prescription slip."""
    model_name = GEMINI_MODEL or "gemini-1.5-flash"
    prompt = """You are a Clinical Pharmacist Assistant.
Extract all visible medications, dosages, frequency, and daily timings from this prescription slip.
Return valid JSON strictly matching:
{
  "doctor_name": "Doctor name or clinic if visible",
  "prescription_date": "Date if visible",
  "medications": [
    {
      "name": "Medication Name",
      "dosage": "e.g. 500mg",
      "frequency": "e.g. Once daily",
      "timing": ["08:00 AM"],
      "instructions": "e.g. With meals",
      "purpose": "Clinical purpose if stated"
    }
  ],
  "clinical_notes": "Any doctor notes or precautions"
}
"""
    mime_type = content_type or "image/jpeg"
    if "pdf" in mime_type:
        mime_type = "application/pdf"

    image_part = {
        "mime_type": mime_type,
        "data": file_bytes
    }

    model = genai.GenerativeModel(
        model_name=model_name,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.1
        )
    )

    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, lambda: model.generate_content([prompt, image_part]))
    text = response.text.strip()
    return json.loads(text)
