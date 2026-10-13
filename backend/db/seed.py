"""
backend/db/seed.py — Seeds realistic demonstration clinical cases into SQLite database.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone, timedelta
from db.database import init_db
from db.repository import (
    create_patient, create_assessment, create_or_update_review,
    create_or_update_care_plan, approve_care_plan, toggle_daily_task_completion,
    get_patient_by_id
)


def seed_demo_data() -> None:
    init_db()
    if get_patient_by_id("demo_pat_01"):
        return  # Already seeded

    now = datetime.now(timezone.utc)
    today_str = now.strftime("%Y-%m-%d")
    yesterday_str = (now - timedelta(days=1)).strftime("%Y-%m-%d")

    # ── Demo Patient 1: John Doe (Pending Review) ──────────────────────────────
    p1 = create_patient(
        name="John Doe",
        age=62,
        sex="male",
        demographics={"occupation": "Accountant", "location": "Urban", "smoking_status": "former"},
        patient_id="demo_pat_01"
    )

    p1_inputs = {
        "age": 62, "sex": "male", "height_cm": 172, "weight_kg": 92.5, "bmi": 31.27,
        "systolic_bp": 152.0, "diastolic_bp": 94.0, "heart_rate": 78.0,
        "fasting_glucose": 158.0, "hba1c": 7.8, "total_cholesterol": 224.0,
        "hdl": 38.0, "ldl": 142.0, "triglycerides": 210.0,
        "creatinine": 1.15, "egfr": 68.0, "alt": 34.0, "ast": 28.0,
        "smoking_status": "former", "hypertension": True, "diabetes_history": True
    }

    p1_results = {
        "diabetes": {
            "disease": "diabetes", "display_name": "Type 2 Diabetes", "icon": "🩺",
            "status": "success",
            "prediction": {"label": "high_risk", "probability": 0.82, "percentage": 82},
            "model": {"provider": "local", "model_id": "ExtraTreesClassifier", "version": "scikit-learn (ROC-AUC: 0.819)"},
            "input_summary": {"data_completeness": 1.0, "features_used": ["glucose", "bmi", "age", "blood_pressure"]},
            "explanation": {
                "available": True,
                "text": "Elevated fasting blood sugar (158 mg/dL) and BMI of 31.3 indicate high risk of glycemic dysregulation.",
                "factors": ["fasting_glucose: 158.0", "bmi: 31.27", "age: 62", "systolic_bp: 152.0"]
            }
        },
        "heart_disease": {
            "disease": "heart_disease", "display_name": "Heart Disease", "icon": "❤️",
            "status": "success",
            "prediction": {"label": "moderate_risk", "probability": 0.58, "percentage": 58},
            "model": {"provider": "local", "model_id": "Balanced LogisticRegression", "version": "scikit-learn (ROC-AUC: 0.964)"},
            "input_summary": {"data_completeness": 0.85, "features_used": ["age", "sex", "trestbps", "chol"]},
            "explanation": {
                "available": True,
                "text": "Stage 2 systolic hypertension (152 mmHg) combined with dyslipidemia elevates cardiovascular risk.",
                "factors": ["trestbps: 152.0", "chol: 224.0", "age: 62"]
            }
        },
        "ckd": {
            "disease": "ckd", "display_name": "Chronic Kidney Disease", "icon": "🫘",
            "status": "success",
            "prediction": {"label": "moderate_risk", "probability": 0.44, "percentage": 44},
            "model": {"provider": "local", "model_id": "RandomForestClassifier", "version": "scikit-learn (ROC-AUC: 1.000 benchmark)"},
            "input_summary": {"data_completeness": 0.65, "features_used": ["age", "bp", "sc", "bgr"]},
            "explanation": {
                "available": True,
                "text": "Mildly decreased eGFR (68 mL/min) with baseline creatinine 1.15 mg/dL suggests early stage 2 kidney strain.",
                "factors": ["sc: 1.15", "bp: 152.0", "bgr: 158.0"]
            }
        },
        "liver_disease": {
            "disease": "liver_disease", "display_name": "Liver Disease", "icon": "🟤",
            "status": "success",
            "prediction": {"label": "low_risk", "probability": 0.22, "percentage": 22},
            "model": {"provider": "local", "model_id": "GradientBoostingClassifier", "version": "scikit-learn (ROC-AUC: 0.764)"},
            "input_summary": {"data_completeness": 0.70, "features_used": ["age", "gender", "alamine_aminotransferase"]},
            "explanation": {
                "available": True,
                "text": "Liver transaminases (ALT 34, AST 28) remain within acceptable physiological reference ranges.",
                "factors": ["alt: 34.0", "ast: 28.0"]
            }
        },
        "stroke": {
            "disease": "stroke", "display_name": "Stroke Risk", "icon": "🧠",
            "status": "success",
            "prediction": {"label": "moderate_risk", "probability": 0.48, "percentage": 48},
            "model": {"provider": "local", "model_id": "calibrated LogisticRegression", "version": "scikit-learn (ROC-AUC: 0.844)"},
            "input_summary": {"data_completeness": 0.90, "features_used": ["age", "hypertension", "avg_glucose_level", "bmi"]},
            "explanation": {
                "available": True,
                "text": "Hypertension and age > 60 elevate cerebrovascular risk index.",
                "factors": ["age: 62", "systolic_bp: 152.0", "fasting_glucose: 158.0"]
            }
        }
    }

    create_assessment(
        patient_id="demo_pat_01",
        inputs=p1_inputs,
        disease_results=p1_results,
        status="pending_review",
        provider="local",
        data_completeness=0.88,
        assessment_id="demo_asm_01"
    )

    create_or_update_review(
        assessment_id="demo_asm_01",
        doctor_name="Dr. Sarah Mitchell, MD",
        status="pending",
        doctor_notes="Patient submitted assessment with fasting blood glucose 158 and BP 152/94. Priority review required for glycemic intervention.",
        requested_tests=["Urine Albumin-to-Creatinine Ratio (UACR)", "Repeat HbA1c in 6 weeks"],
        review_id="demo_rev_01"
    )

    # ── Demo Patient 2: Eleanor Vance (Reviewed with Draft Plan) ────────────────
    create_patient(
        name="Eleanor Vance",
        age=54,
        sex="female",
        demographics={"occupation": "High School Principal", "location": "Suburban", "smoking_status": "never"},
        patient_id="demo_pat_02"
    )

    p2_inputs = {
        "age": 54, "sex": "female", "height_cm": 164, "weight_kg": 76.0, "bmi": 28.26,
        "systolic_bp": 144.0, "diastolic_bp": 88.0, "heart_rate": 74.0,
        "fasting_glucose": 104.0, "total_cholesterol": 248.0, "hdl": 44.0, "ldl": 162.0, "triglycerides": 185.0,
        "creatinine": 0.85, "egfr": 92.0, "alt": 22.0, "ast": 20.0,
        "smoking_status": "never", "hypertension": True, "family_history_heart_disease": True
    }

    p2_results = {
        "diabetes": {
            "disease": "diabetes", "display_name": "Type 2 Diabetes", "icon": "🩺",
            "status": "success",
            "prediction": {"label": "low_risk", "probability": 0.24, "percentage": 24},
            "model": {"provider": "local", "model_id": "ExtraTreesClassifier"},
            "explanation": {"available": True, "factors": ["glucose: 104.0", "bmi: 28.26"]}
        },
        "heart_disease": {
            "disease": "heart_disease", "display_name": "Heart Disease", "icon": "❤️",
            "status": "success",
            "prediction": {"label": "high_risk", "probability": 0.72, "percentage": 72},
            "model": {"provider": "local", "model_id": "Balanced LogisticRegression"},
            "explanation": {"available": True, "factors": ["chol: 248.0", "ldl: 162.0", "systolic_bp: 144.0"]}
        },
        "ckd": {
            "disease": "ckd", "display_name": "Chronic Kidney Disease", "icon": "🫘",
            "status": "success",
            "prediction": {"label": "low_risk", "probability": 0.12, "percentage": 12},
            "model": {"provider": "local", "model_id": "RandomForestClassifier"},
            "explanation": {"available": True, "factors": ["egfr: 92.0", "creatinine: 0.85"]}
        },
        "liver_disease": {
            "disease": "liver_disease", "display_name": "Liver Disease", "icon": "🟤",
            "status": "success",
            "prediction": {"label": "low_risk", "probability": 0.15, "percentage": 15},
            "model": {"provider": "local", "model_id": "GradientBoostingClassifier"},
            "explanation": {"available": True, "factors": ["alt: 22.0", "ast: 20.0"]}
        },
        "stroke": {
            "disease": "stroke", "display_name": "Stroke Risk", "icon": "🧠",
            "status": "success",
            "prediction": {"label": "moderate_risk", "probability": 0.38, "percentage": 38},
            "model": {"provider": "local", "model_id": "calibrated LogisticRegression"},
            "explanation": {"available": True, "factors": ["systolic_bp: 144.0", "age: 54"]}
        }
    }

    create_assessment(
        patient_id="demo_pat_02",
        inputs=p2_inputs,
        disease_results=p2_results,
        status="reviewed",
        provider="local",
        data_completeness=0.82,
        assessment_id="demo_asm_02"
    )

    create_or_update_review(
        assessment_id="demo_asm_02",
        doctor_name="Dr. Sarah Mitchell, MD",
        status="reviewed",
        doctor_notes="Cardiovascular risk driven by LDL 162 mg/dL and Stage 1 hypertension. Initiated dietary lipid management draft plan.",
        requested_tests=["Comprehensive Lipid Subfraction Panel"],
        review_id="demo_rev_02"
    )

    # Draft Care Plan for Eleanor Vance
    create_or_update_care_plan(
        patient_id="demo_pat_02",
        assessment_id="demo_asm_02",
        diet={
            "foods_to_eat": ["Oat bran, chia seeds, and soluble fiber", "Wild salmon and omega-3 rich fish", "Extra virgin olive oil", "Leafy greens and berries"],
            "foods_to_avoid": ["Saturated fats, palm oil, and butter", "Ultra-processed fried foods", "Excess sodium (> 2000mg/day)"],
            "hydration": "Drink 2.5L water daily; limit caffeine after 2 PM."
        },
        exercise={
            "protocol": "Moderate cardiovascular conditioning (Brisk walking / cycling)",
            "frequency": "30 minutes, 5 days per week",
            "target_heart_rate": "110 - 130 bpm",
            "caution": "Avoid sudden high-intensity sprints until blood pressure normalizes."
        },
        schedule=[
            {"time": "07:30 AM", "period": "Morning", "category": "nutrition", "task": "Heart-healthy oatmeal with chia seeds and walnuts"},
            {"time": "08:15 AM", "period": "Morning", "category": "vitals", "task": "Resting blood pressure log (target < 130/85)"},
            {"time": "12:30 PM", "period": "Midday", "category": "nutrition", "task": "Mediterranean tuna salad with mixed greens & olive oil"},
            {"time": "05:30 PM", "period": "Evening", "category": "exercise", "task": "30-minute brisk outdoor aerobic walk"},
            {"time": "07:30 PM", "period": "Evening", "category": "nutrition", "task": "Steamed broccoli and grilled chicken breast"},
            {"time": "10:30 PM", "period": "Bedtime", "category": "sleep", "task": "7.5 hours uninterrupted restorative sleep window"}
        ],
        status="draft",
        doctor_comments="Draft plan created. Pending final patient discussion before publishing.",
        plan_id="demo_cpl_02"
    )

    # ── Demo Patient 3: Robert Chen (Approved Plan & Active Progress) ───────────
    create_patient(
        name="Robert Chen",
        age=48,
        sex="male",
        demographics={"occupation": "Civil Engineer", "location": "Urban", "smoking_status": "never"},
        patient_id="demo_pat_03"
    )

    p3_inputs = {
        "age": 48, "sex": "male", "height_cm": 175, "weight_kg": 84.0, "bmi": 27.43,
        "systolic_bp": 136.0, "diastolic_bp": 86.0, "heart_rate": 72.0,
        "fasting_glucose": 112.0, "total_cholesterol": 198.0, "hdl": 46.0, "ldl": 124.0,
        "creatinine": 1.32, "egfr": 64.0, "bun": 22.0, "alt": 26.0, "ast": 24.0,
        "urine_protein": 35.0, "hypertension": True, "family_history_kidney_disease": True
    }

    p3_results = {
        "diabetes": {"disease": "diabetes", "display_name": "Type 2 Diabetes", "status": "success", "prediction": {"label": "moderate_risk", "probability": 0.42, "percentage": 42}},
        "heart_disease": {"disease": "heart_disease", "display_name": "Heart Disease", "status": "success", "prediction": {"label": "moderate_risk", "probability": 0.48, "percentage": 48}},
        "ckd": {"disease": "ckd", "display_name": "Chronic Kidney Disease", "status": "success", "prediction": {"label": "high_risk", "probability": 0.68, "percentage": 68}},
        "liver_disease": {"disease": "liver_disease", "display_name": "Liver Disease", "status": "success", "prediction": {"label": "low_risk", "probability": 0.18, "percentage": 18}},
        "stroke": {"disease": "stroke", "display_name": "Stroke Risk", "status": "success", "prediction": {"label": "low_risk", "probability": 0.31, "percentage": 31}}
    }

    create_assessment(
        patient_id="demo_pat_03",
        inputs=p3_inputs,
        disease_results=p3_results,
        status="care_plan_approved",
        provider="local",
        data_completeness=0.85,
        assessment_id="demo_asm_03"
    )

    create_or_update_review(
        assessment_id="demo_asm_03",
        doctor_name="Dr. Sarah Mitchell, MD",
        status="reviewed",
        doctor_notes="Chronic kidney risk stage 2 confirmed with microalbuminuria. Approved nephrology-protective lifestyle protocol.",
        requested_tests=["24-hour Urine Protein", "Serum Electrolytes"],
        review_id="demo_rev_03"
    )

    p3_plan = create_or_update_care_plan(
        patient_id="demo_pat_03",
        assessment_id="demo_asm_03",
        diet={
            "foods_to_eat": ["Low-phosphorus foods (cauliflower, apples, berries)", "Plant-based proteins and moderate egg whites", "Adequate hydration with filtered water"],
            "foods_to_avoid": ["High-sodium canned foods and bouillon cubes", "NSAID pain relievers (ibuprofen/naproxen)", "Excess phosphorus and dark colas"],
            "hydration": "Structured 2.0L fluid intake evenly spaced throughout day."
        },
        exercise={
            "protocol": "Low-impact endurance and mobility training",
            "frequency": "25 minutes walking or swimming, 4-5 days/week",
            "caution": "Avoid dehydration during heat; rest if fatigued."
        },
        schedule=[
            {"time": "08:00 AM", "period": "Morning", "category": "nutrition", "task": "Renal-friendly berry smoothie with oat milk"},
            {"time": "08:30 AM", "period": "Morning", "category": "vitals", "task": "Morning Blood Pressure & Pulse log"},
            {"time": "11:00 AM", "period": "Midday", "category": "hydration", "task": "Drink 500ml water and 10-minute mobility stretch"},
            {"time": "01:00 PM", "period": "Midday", "category": "nutrition", "task": "Steamed white rice, tofu stir-fry, and zucchini"},
            {"time": "06:00 PM", "period": "Evening", "category": "exercise", "task": "25-minute brisk neighborhood walk"},
            {"time": "07:30 PM", "period": "Evening", "category": "nutrition", "task": "Grilled white fish with roasted cauliflower"},
            {"time": "10:00 PM", "period": "Bedtime", "category": "sleep", "task": "Bedtime relaxation and 8-hour sleep routine"}
        ],
        status="draft",
        doctor_comments="Approved comprehensive renal care plan. Adhere to daily hydration and blood pressure tracking.",
        plan_id="demo_cpl_03"
    )

    approve_care_plan("demo_cpl_03", approved_by="Dr. Sarah Mitchell, MD")

    # Seed progress for Robert Chen
    # Yesterday: completed 5 of 7 tasks
    toggle_daily_task_completion("demo_pat_03", "demo_cpl_03", yesterday_str, "task_1", "nutrition", "Renal-friendly berry smoothie", True)
    toggle_daily_task_completion("demo_pat_03", "demo_cpl_03", yesterday_str, "task_2", "vitals", "Morning Blood Pressure log", True)
    toggle_daily_task_completion("demo_pat_03", "demo_cpl_03", yesterday_str, "task_3", "hydration", "500ml water and stretch", True)
    toggle_daily_task_completion("demo_pat_03", "demo_cpl_03", yesterday_str, "task_4", "nutrition", "Tofu stir-fry lunch", True)
    toggle_daily_task_completion("demo_pat_03", "demo_cpl_03", yesterday_str, "task_5", "exercise", "25-minute brisk walk", True)
    toggle_daily_task_completion("demo_pat_03", "demo_cpl_03", yesterday_str, "task_6", "nutrition", "Grilled white fish dinner", False)
    toggle_daily_task_completion("demo_pat_03", "demo_cpl_03", yesterday_str, "task_7", "sleep", "Bedtime sleep routine", False)

    # Today: completed morning tasks
    toggle_daily_task_completion("demo_pat_03", "demo_cpl_03", today_str, "task_1", "nutrition", "Renal-friendly berry smoothie", True)
    toggle_daily_task_completion("demo_pat_03", "demo_cpl_03", today_str, "task_2", "vitals", "Morning Blood Pressure log", True)
    toggle_daily_task_completion("demo_pat_03", "demo_cpl_03", today_str, "task_3", "hydration", "500ml water and stretch", False)
    toggle_daily_task_completion("demo_pat_03", "demo_cpl_03", today_str, "task_4", "nutrition", "Tofu stir-fry lunch", False)
    toggle_daily_task_completion("demo_pat_03", "demo_cpl_03", today_str, "task_5", "exercise", "25-minute brisk walk", False)
    toggle_daily_task_completion("demo_pat_03", "demo_cpl_03", today_str, "task_6", "nutrition", "Grilled white fish dinner", False)
    toggle_daily_task_completion("demo_pat_03", "demo_cpl_03", today_str, "task_7", "sleep", "Bedtime sleep routine", False)
