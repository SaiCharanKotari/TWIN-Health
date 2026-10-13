# TwinHealth AI — Digital Twin Clinical Platform

TwinHealth AI is a full-stack, local-first digital-twin healthcare platform for chronic disease risk prediction, clinician assessment, and personalized lifestyle tracking.

The platform connects distinct patient and clinician experiences through an atomic, thread-safe **Local JSON Persistence Engine** in `data/` and runs all five disease risk models locally using trained scikit-learn pipelines without external cloud API dependencies.

---

## 1. Application Flow & Routes

```
                          ┌─────────────────────────────┐
                          │   Public Landing Page (/)   │
                          │   • 5 ML Disease Models     │
                          │   • Digital Twin Concept    │
                          │   • Find Nearby Care (Maps) │
                          └──────────────┬──────────────┘
                                         │ Click "Sign In / Login"
                                         ▼
                          ┌─────────────────────────────┐
                          │   Portal Login (/login)     │
                          │   Choose: Patient or Doctor │
                          │   Enter email address       │
                          └──────┬───────────────┬──────┘
                                 │               │
               Selected "Doctor" │               │ Selected "Patient"
                                 ▼               ▼
┌──────────────────────────────────────┐   ┌──────────────────────────────────────┐
│  Clinician Workspace (/input)        │   │  Patient Companion (/patient)        │
│  • Mandatory Patient Email at top    │   │  • Log in with SAME patient email    │
│  • Enter vitals & lab biomarkers     │   │  • View 24-hr chronotherapy routine  │
│  • Run 5 local ML disease models     │   │  • Check off daily activities        │
│  • Saves to data/assessments.json    │   │  • Instant sync to JSON persistence  │
└──────────────────┬───────────────────┘   └──────────────────▲───────────────────┘
                   │ Auto-redirect                            │
                   ▼                                          │
┌──────────────────────────────────────┐                      │
│  Results Page (/results?assessmentId)│                      │
│  • Reads ?assessmentId=<id> from URL │                      │
│  • Displays 5 model risk scores      │                      │
│  • [Patient Activity Planning] button│                      │
│  • [New Assessment] button           │                      │
└──────────────────┬───────────────────┘                      │
                   │ Click "Patient Activity Planning"        │
                   ▼                                          │
┌──────────────────────────────────────┐                      │
│  Doctor Activity View                │                      │
│  (/doctor/activity?patientEmail=...) │                      │
│  • Live adherence score (% bar)      │                      │
│  • Planned vs patient-checked tasks  │──────────────────────┘
│  • "Refresh Activity" live sync      │  Synchronized across separate tabs,
└──────────────────────────────────────┘  browsers, and profiles
```

---

## 2. Routes Summary

| Route | Role | Description |
| :--- | :--- | :--- |
| **`/`** | Public | Public landing page explaining digital twin concept, 5 disease models, workflows, and Google Maps search for nearby diagnostic labs. |
| **`/login`** | Public | Role selection (`Patient` or `Doctor`) and email address entry. Stores session in `data/users.json`. |
| **`/input`** | Clinician | Clinical intake form with mandatory **Patient Email Address** field at the top, CSV/Excel upload, and local ML inference. |
| **`/results?assessmentId=<id>`** | Clinician | Persistent risk results page fetching exact assessment from backend. Has `Patient Activity Planning` and `New Assessment` actions. |
| **`/doctor/activity?patientEmail=...`** | Clinician | Read-only physician monitoring dashboard showing patient-reported completion, exercise adherence, medication compliance, and weekly history. |
| **`/patient`** | Patient | Patient lifestyle companion with date navigation, chronotherapy checklist (morning, afternoon, evening, bedtime), and adherence telemetry. |
| **`/doctor`** | Clinician | Classical clinical queue table and biomarker inspector. |

---

## 3. Local JSON Storage Structure (`data/`)

Persistent data is stored in JSON files at the project root (`data/`), resolved independently of the current shell working directory:

- **`data/users.json`**: Email demo identities, roles (`patient` or `doctor`), display names, timestamps.
- **`data/patients.json`**: Demographic records keyed by normalized patient email and patient ID.
- **`data/assessments.json`**: Clinical inputs, normalized features, 5 disease outputs, completeness scores, linked care plan IDs.
- **`data/care_plans.json`**: Structured chronotherapy schedules with stable task IDs, periods, categories, and clinician instructions.
- **`data/activity_completions.json`**: Date-specific task completion events (`completed: true/false`, timestamp, category, title).

### Thread Safety & Atomic Writes
- Writes are serialized using in-process `threading.Lock()`.
- Data is written to temporary files and atomically replaced via `os.replace()`, preventing file corruption during power interruptions or concurrent requests.

---

## 4. Five Local Machine Learning Pipelines

All 5 clinical pipelines run **100% locally** using scikit-learn artifacts without external cloud dependencies or API keys:

| Condition | Training Dataset | Pipeline Architecture | Benchmark Metric | Clinical Reality & Caveats |
| :--- | :--- | :--- | :--- | :--- |
| **Type 2 Diabetes** | Pima Indians Diabetes | SimpleImputer + StandardScaler + LogisticRegression | ~0.83 ROC-AUC | Metabolic baseline; requires fasting glucose or HbA1c. |
| **Heart Disease** | Cleveland Heart Disease | StandardScaler + RandomForestClassifier | ~0.90 ROC-AUC | Validated on clinical parameters (blood pressure, cholesterol, resting ECG). |
| **Chronic Kidney Disease (CKD)** | UCI CKD Dataset | ColumnTransformer + Imputer + ExtraTreesClassifier | 0.99–1.00 ROC-AUC | **Benchmark Artifact:** Extremely high score due to collinear diagnostic lab features (serum creatinine, specific gravity). Strict sufficiency enforces `insufficient_data` when labs are absent. |
| **Liver Disease** | Indian Liver Patient (ILPD) | Median Imputer + GradientBoostingClassifier | ~0.76 ROC-AUC | Moderate discrimination due to enzyme variance (ALT, AST, total bilirubin). |
| **Stroke Risk** | Kaggle Stroke Prediction | OneHotEncoder + StandardScaler + LogisticRegression | ~0.84 ROC-AUC | **Severe Class Imbalance:** ~5% stroke prevalence in population; probability calibration adjusted for screening sensitivity. |

---

## 5. Startup & Running the Application

### Single Windows Startup Script
Double-click or run from command prompt:
```cmd
.\run.bat
```
*The script automatically provisions default `.env`, checks dependencies in `requirements.txt`, and boots the FastAPI server at `http://localhost:8000`.*

### Manual Startup
```bash
pip install -r requirements.txt
cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

---

## 6. Two-Browser Testing Guide

Open **Browser A** (Clinician) and **Browser B** (Patient, incognito or separate browser profile) pointing to the same server at `http://localhost:8000`:

1. **In Browser A (Clinician):**
   - Open `http://localhost:8000/`.
   - Click **Sign In / Login** in the top navigation.
   - Select **Clinician / Doctor**, enter `doctor@twinhealth.demo`, and click **Continue**.
   - You will be redirected to `/input`.
   - In the mandatory **Patient Email Address** field at the top, enter a test patient email: `patient.test@example.com`.
   - Fill in age (e.g. `52`), blood pressure (e.g. `140/90`), glucose (`130`), etc.
   - Click **Run 5-Disease Detection**.
   - You will be redirected to `/results?assessmentId=<id>`.
   - Notice the **Patient Activity Planning** button in the toolbar.

2. **In Browser B (Patient):**
   - Open `http://localhost:8000/`.
   - Click **Sign In / Login**.
   - Select **Patient**, enter the EXACT same email: `patient.test@example.com`.
   - Click **Continue** -> redirected to `/patient`.
   - The patient's 24-hour chronotherapy schedule appears (Morning, Afternoon, Evening, Bedtime).
   - Check off one of the activities (e.g. Morning Zone-2 Walk or Hydration).
   - Notice the adherence percentage bar immediately updates.

3. **In Browser A (Clinician):**
   - On the results page, click **Patient Activity Planning** (or open `/doctor/activity?patientEmail=patient.test@example.com`).
   - Click **Refresh Activity** (or wait 10 seconds for auto-refresh).
   - The task checked off by the patient in Browser B now displays: `✓ Marked Complete by Patient` with adherence metrics updated in real time!

---

## 7. Automated Test Suite

Run the full pytest suite (49 automated tests covering data adapters, model pipelines, local JSON storage, and end-to-end multi-user flows):
```bash
python -m pytest tests/ -v
```

---

## 8. Limitations & Security Notice

**IMPORTANT:** Email-based identity in this application is for local development and academic demonstration only. It does **NOT** provide HIPAA, SOC2, or cryptographic password authentication. Never input real Protected Health Information (PHI) in this demo environment. A production deployment requires OAuth2/OIDC, multi-factor authentication, database-level encryption at rest, and audit logging.
