# TwinHealth AI — Clinical Assessment Server

TwinHealth AI is an academic, multi-disease risk assessment system. It accepts patient data (demographics, vitals, bloodwork) and uses AI to estimate the risk for five major diseases:
- **Type 2 Diabetes**
- **Heart Disease**
- **Chronic Kidney Disease (CKD)**
- **Liver Disease**
- **Stroke Risk**

The system is built with FastAPI on the backend and features a modern, interactive vanilla JavaScript/CSS frontend. It dynamically supports incomplete data (Preliminary Risk Checks) and full clinical data (Advanced Checks).

## Features

- **Multi-Disease Models**: Simultaneously evaluates data against 5 clinical guidelines (ADA, Framingham, KDIGO, etc.).
- **Preliminary vs. Advanced**: Missing clinical lab data? The system will still provide a preliminary estimate based on demographics, and generate a Referral Form indicating what bloodwork is needed for a more accurate assessment.
- **AI-Powered**: Integrates with Google Gemini AI (`gemini-1.5-flash`) for clinical reasoning and risk factor extraction.
- **Doctor Follow-up Tools**: Includes Google Maps integration to find nearby clinics, and auto-generates printable Clinical Referral Forms for physicians.
- **Bulk Upload**: Supports `.csv` and `.xlsx` file uploads for rapid data entry.

## Prerequisites

- Python 3.9+
- A Google Gemini API Key (get one from [Google AI Studio](https://aistudio.google.com/))

## Setup & Running Locally

1. **Configure Environment variables:**
   Copy the `.env.example` file to a new file named `.env`:
   ```bash
   cp .env.example .env
   ```
   Open `.env` and set your `GEMINI_API_KEY`.

2. **Run the application:**
   You can run the application on Windows by simply executing the batch script:
   ```cmd
   .\run.bat
   ```
   *This script automatically installs the required Python dependencies (FastAPI, Uvicorn, Google Generative AI SDK, etc.) and starts the server.*

3. **Access the Application:**
   - **Frontend UI:** [http://localhost:8000](http://localhost:8000)
   - **API Documentation:** [http://localhost:8000/docs](http://localhost:8000/docs)
   - **Health Check:** [http://localhost:8000/health](http://localhost:8000/health)

## Project Structure

- `backend/` - FastAPI server, API routes, Disease Adapters, AI Prompts.
  - `main.py` - Application entry point.
  - `models/registry.py` - Configuration for disease model requirements.
  - `providers/gemini_provider.py` - Integration and prompts for Gemini.
- `frontend/` - Static assets served directly by FastAPI.
  - `index.html` - The main interface.
  - `clinical-form.html` - Printable hospital intake form.
  - `app.js`, `form.js`, `results.js` - Client-side logic.
- `tests/` - Pytest unit tests for data adapters and logic.

## Disclaimer
This system is an academic AI-based prediction tool and is **NOT** a substitute for professional medical diagnosis or treatment.
