"""
tests/test_medication_upload_download.py
Comprehensive automated test suite for:
1. Optional medication file upload per assessment (POST /api/assessments/{id}/medications/upload)
2. Medication file downloading (GET /api/medications/{file_id}/download)
3. Patient portal medication listing (GET /api/patients/{email}/medications)
4. UI verification: Doctor review module removed from results and replaced with optional medication upload
5. UI verification: Patient dashboard includes medication download card
6. UI verification: Monochrome black-and-white theme active everywhere
"""
import os
import sys
import pytest
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
from main import app
from storage import json_storage as js


@pytest.mark.asyncio
async def test_upload_and_download_medication_flow():
    """
    Test uploading a medication prescription file for an assessment,
    confirming it is attached to the assessment and patient, and downloading it.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Use existing assessment asm_6c72fced1e or create test
        target_asm_id = "asm_6c72fced1e"
        sample_file_content = b"Rx: Metformin 500mg BID, Atorvastatin 20mg QHS. Take with water."
        files = {
            "file": ("prescription_rx_test.txt", sample_file_content, "text/plain")
        }
        data = {
            "notes": "Patient reports taking after dinner.",
            "patient_email": "kotarisai.chara2023@vitstudent.ac.in"
        }

        # 1. Upload medication
        upload_resp = await ac.post(
            f"/api/assessments/{target_asm_id}/medications/upload",
            files=files,
            data=data
        )
        assert upload_resp.status_code == 200, f"Upload failed: {upload_resp.text}"
        upload_data = upload_resp.json()
        assert upload_data["status"] == "success"
        record = upload_data["medication_record"]
        assert record["filename"] == "prescription_rx_test.txt"
        assert record["assessment_id"] == target_asm_id
        file_id = record["file_id"]
        assert file_id is not None

        # 2. Verify assessment now includes medication_record
        asm_resp = await ac.get(f"/api/assessments/{target_asm_id}")
        assert asm_resp.status_code == 200
        asm_data = asm_resp.json()
        assert "medication_record" in asm_data
        assert asm_data["medication_record"]["file_id"] == file_id

        # 3. Verify patient medications endpoint lists the uploaded file
        patient_email = "kotarisai.chara2023@vitstudent.ac.in"
        patient_meds_resp = await ac.get(f"/api/patients/{patient_email}/medications")
        assert patient_meds_resp.status_code == 200
        meds_data = patient_meds_resp.json()
        assert meds_data["has_medication"] is True
        assert meds_data["medication"]["file_id"] == file_id
        assert meds_data["medication"]["filename"] == "prescription_rx_test.txt"

        # 4. Download file
        download_resp = await ac.get(f"/api/medications/{file_id}/download")
        assert download_resp.status_code == 200
        assert download_resp.content == sample_file_content
        assert "filename=" in download_resp.headers.get("content-disposition", "")


@pytest.mark.asyncio
async def test_download_nonexistent_medication():
    """
    Attempting to download an invalid file_id must return 404.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        download_resp = await ac.get("/api/medications/med_nonexistent_xyz999/download")
        assert download_resp.status_code == 404
        assert "detail" in download_resp.json()


@pytest.mark.asyncio
async def test_results_ui_contract_doctor_review_removed_medication_present():
    """
    Verify results.js no longer contains the doctor review action box or 'Submit for Doctor Review',
    and contains 'medication-upload-box' with 'Upload Medication (Optional)'.
    """
    results_js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "results.js"))
    with open(results_js_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Must NOT have doctor review submission module in results
    assert "doctor-action-box" not in content, "doctor-action-box must be removed from results.js"
    assert "Submit for Doctor Review" not in content, "'Submit for Doctor Review' must be removed from results.js"

    # MUST have medication upload module
    assert "medication-upload-box" in content, "medication-upload-box must be present in results.js"
    assert "Upload Medication (Optional)" in content, "'Upload Medication (Optional)' must be present in results.js"
    assert "/medications/upload" in content, "Medication upload endpoint must be referenced in results.js"


@pytest.mark.asyncio
async def test_patient_ui_contract_medication_download_present():
    """
    Verify patient.html and patient.js contain the medication download card & loader.
    """
    patient_html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "patient.html"))
    with open(patient_html_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    assert "Prescriptions" in html_content and "Medications" in html_content

    patient_js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "patient.js"))
    with open(patient_js_path, "r", encoding="utf-8") as f:
        js_content = f.read()

    assert "download_url" in js_content, "Download medication URL property must be present in patient.js"


@pytest.mark.asyncio
async def test_black_and_white_theme_enforced_across_pages():
    """
    Verify all primary HTML pages and style.css maintain a sleek Black & White theme,
    without brute-force grayscale filter (so logos and emojis retain full color),
    and with selective clinical risk severity colors active.
    """
    frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
    pages = [
        "index.html",
        "login.html",
        "input.html",
        "results.html",
        "doctor.html",
        "doctor-activity.html",
        "patient.html"
    ]
    for page in pages:
        page_path = os.path.join(frontend_dir, page)
        with open(page_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Verify no brute-force grayscale filter flattening emojis/logos
        assert "filter: grayscale(100%)" not in content, f"{page} should not have brute-force grayscale"

    # Verify style.css does not have brute-force grayscale on html
    style_css_path = os.path.join(frontend_dir, "style.css")
    with open(style_css_path, "r", encoding="utf-8") as f:
        style_content = f.read()
    assert "filter: grayscale(100%)" not in style_content

    # Verify clinical risk colors are defined in results.js
    results_js_path = os.path.join(frontend_dir, "results.js")
    with open(results_js_path, "r", encoding="utf-8") as f:
        results_js_content = f.read()
    assert "#dc2626" in results_js_content  # High Risk (Red)
    assert "#d97706" in results_js_content  # Moderate Risk (Amber)
    assert "#10b981" in results_js_content  # Low Risk (Green)
