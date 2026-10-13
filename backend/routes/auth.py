"""
backend/routes/auth.py — Email-based local demo identity and role routing endpoints.

Note: This is an email-based local demonstration mechanism for development and testing.
It does NOT provide HIPAA/SOC2 compliance or real cryptographic authentication.
"""
from __future__ import annotations
import re
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

try:
    from storage import json_storage as js
except ImportError:
    from backend.storage import json_storage as js

router = APIRouter(prefix="/api/auth", tags=["auth"])

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class DemoLoginRequest(BaseModel):
    email: str = Field(..., description="User's email address")
    role: str = Field(..., description="Role: 'patient' or 'doctor'")
    display_name: Optional[str] = None


@router.post("/demo-login")
def demo_login(payload: DemoLoginRequest) -> Dict[str, Any]:
    raw_email = (payload.email or "").strip()
    if not raw_email or not EMAIL_REGEX.match(raw_email):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Please provide a valid email address (e.g., user@example.com)."
        )

    role = payload.role.strip().lower()
    if role not in ("patient", "doctor"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Role must be either 'patient' or 'doctor'."
        )

    norm_email = js.normalize_email(raw_email)
    user = js.upsert_user(norm_email, role=role, display_name=payload.display_name or "")

    # If patient, ensure patient record exists in data/patients.json
    if role == "patient":
        pat = js.get_patient_by_email(norm_email)
        if not pat:
            js.upsert_patient(email=norm_email, name=user.get("display_name"))
        redirect_url = "/patient"
    else:
        redirect_url = "/input"

    return {
        "status": "success",
        "email": norm_email,
        "role": role,
        "display_name": user.get("display_name"),
        "redirect_url": redirect_url,
        "disclaimer": "Local demo session created. Stored in data/users.json."
    }


@router.get("/users")
def get_demo_users() -> Dict[str, Any]:
    """Returns stored demo users for easy role switching."""
    users = js.list_users()
    return {
        "users": users,
        "count": len(users)
    }
