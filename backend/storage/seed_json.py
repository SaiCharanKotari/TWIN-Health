"""
backend/storage/seed_json.py — Seed realistic local demo records into data/ JSON files.
"""
from __future__ import annotations
import logging
try:
    from storage import json_storage as js
except ImportError:
    from backend.storage import json_storage as js

logger = logging.getLogger("twinhealth.storage.seed")


def seed_demo_data_if_empty() -> None:
    """Pre-seeds standard clinical demo users, patients, assessments, and care plans."""
    js.init_storage()

    users = js.list_users()
    if users:
        # Already seeded
        return

    logger.info("Pre-seeding realistic clinical demo records into data/*.json...")

    # 1. Clinician Demo User
    js.upsert_user("doctor@twinhealth.demo", role="doctor", display_name="Dr. Sarah Mitchell, MD")

    # 2. Patient 1: John Doe (Active Metabolic Syndrome, draft care plan)
    p1 = js.upsert_patient(
        email="john.doe@example.com",
        name="John Doe",
        age=58,
        sex="male",
        demographics={"occupation": "Accountant", "smoking_status": "former", "activity_level": "low"},
        patient_id="pat_demo_01"
    )
    js.upsert_user("john.doe@example.com", role="patient", display_name="John Doe")

    asm_inputs_1 = {
        "age": 58, "sex": "male", "height_cm": 175, "weight_kg": 92, "bmi": 30.0,
        "systolic_bp": 145, "diastolic_bp": 92, "fasting_glucose": 138, "hba1c": 7.4,
        "total_cholesterol": 230, "hdl": 38, "ldl": 148, "triglycerides": 220,
        "egfr": 82, "creatinine": 1.1, "alt": 42, "ast": 38
    }
    asm_res_1 = {
        "diabetes": {"status": "success", "prediction": {"label": "high_risk", "percentage": 78, "probability": 0.78}},
        "heart_disease": {"status": "success", "prediction": {"label": "high_risk", "percentage": 72, "probability": 0.72}},
        "stroke": {"status": "success", "prediction": {"label": "moderate_risk", "percentage": 44, "probability": 0.44}},
        "ckd": {"status": "success", "prediction": {"label": "low_risk", "percentage": 22, "probability": 0.22}},
        "liver_disease": {"status": "success", "prediction": {"label": "moderate_risk", "percentage": 52, "probability": 0.52}}
    }
    asm_1 = js.create_assessment(
        patient_id=p1["id"],
        patient_email=p1["email"],
        doctor_email="doctor@twinhealth.demo",
        inputs=asm_inputs_1,
        disease_results=asm_res_1,
        status="completed",
        provider="local",
        data_completeness=0.92,
        assessment_id="asm_demo_01"
    )

    # 3. Patient 2: Robert Chen (Renal & Hypertensive, Approved Plan with active tasks)
    p2 = js.upsert_patient(
        email="robert.chen@example.com",
        name="Robert Chen",
        age=52,
        sex="male",
        demographics={"occupation": "Architect", "smoking_status": "never", "activity_level": "moderate"},
        patient_id="pat_demo_02"
    )
    js.upsert_user("robert.chen@example.com", role="patient", display_name="Robert Chen")

    asm_inputs_2 = {
        "age": 52, "sex": "male", "height_cm": 172, "weight_kg": 76, "bmi": 25.7,
        "systolic_bp": 138, "diastolic_bp": 88, "fasting_glucose": 105, "hba1c": 5.9,
        "total_cholesterol": 195, "hdl": 45, "ldl": 118, "triglycerides": 160,
        "egfr": 58, "creatinine": 1.45, "alt": 28, "ast": 24
    }
    asm_res_2 = {
        "diabetes": {"status": "success", "prediction": {"label": "moderate_risk", "percentage": 42, "probability": 0.42}},
        "heart_disease": {"status": "success", "prediction": {"label": "moderate_risk", "percentage": 54, "probability": 0.54}},
        "ckd": {"status": "success", "prediction": {"label": "high_risk", "percentage": 82, "probability": 0.82}},
        "stroke": {"status": "success", "prediction": {"label": "moderate_risk", "percentage": 38, "probability": 0.38}},
        "liver_disease": {"status": "success", "prediction": {"label": "low_risk", "percentage": 18, "probability": 0.18}}
    }
    asm_2 = js.create_assessment(
        patient_id=p2["id"],
        patient_email=p2["email"],
        doctor_email="doctor@twinhealth.demo",
        inputs=asm_inputs_2,
        disease_results=asm_res_2,
        status="completed",
        provider="local",
        data_completeness=0.95,
        assessment_id="asm_demo_02"
    )

    plan_2 = js.create_or_update_care_plan(
        patient_email=p2["email"],
        patient_id=p2["id"],
        assessment_id=asm_2["id"],
        plan_dict={
            "title": "Comprehensive Renal & Cardiovascular Lifestyle Plan",
            "summary": "Personalized low-sodium, renal-protective chronotherapy regimen with moderate Zone-2 cardio.",
            "active_risks": {"high_risk": [{"name": "Chronic Kidney Disease", "percentage": 82}]},
            "diet": {
                "strategy_name": "Renal & Endothelial Protection Protocol",
                "daily_hydration": "2.0 Liters filtered water throughout daytime",
                "foods_to_eat": ["Low-potassium berries", "Cauliflower and zucchini", "Plant-based proteins"],
                "foods_to_avoid": ["High-sodium packaged foods", "NSAID pain relievers", "Dark colas"]
            },
            "exercise": {
                "regimen_name": "Low-Impact Zone-2 Endurance & Mobility",
                "weekly_goal_mins": 150,
                "daily_exercises": [{"name": "Brisk neighborhood walk", "duration": "30 mins"}]
            },
            "chronotherapy_schedule": [
                {
                    "task_id": "task_1",
                    "time": "07:30 AM",
                    "period": "Morning",
                    "category": "hydration",
                    "title": "Circadian Hydration & Electrolytes",
                    "action": "Drink 400ml filtered water upon waking to kickstart renal filtration.",
                    "icon": "💧"
                },
                {
                    "task_id": "task_2",
                    "time": "08:00 AM",
                    "period": "Morning",
                    "category": "exercise",
                    "title": "Zone-2 Morning Walk (30 mins)",
                    "action": "Brisk 30-minute outdoor walk in natural sunlight.",
                    "icon": "🏃"
                },
                {
                    "task_id": "task_3",
                    "time": "08:45 AM",
                    "period": "Morning",
                    "category": "diet",
                    "title": "Renal-Protective Breakfast",
                    "action": "Steel-cut oatmeal with blueberries, chia seeds, and unsweetened almond milk.",
                    "icon": "🥗"
                },
                {
                    "task_id": "task_4",
                    "time": "01:00 PM",
                    "period": "Afternoon",
                    "category": "diet",
                    "title": "Cardiometabolic Balanced Lunch",
                    "action": "Quinoa bowl with steamed vegetables, tofu, and extra virgin olive oil dressing.",
                    "icon": "🍱"
                },
                {
                    "task_id": "task_5",
                    "time": "05:30 PM",
                    "period": "Evening",
                    "category": "exercise",
                    "title": "Bodyweight Mobility & Core Activation",
                    "action": "15 minutes of gentle postural stretching and bodyweight squats.",
                    "icon": "🏋️"
                },
                {
                    "task_id": "task_6",
                    "time": "07:30 PM",
                    "period": "Evening",
                    "category": "diet",
                    "title": "Light Anti-Inflammatory Dinner",
                    "action": "Grilled white fish or lentils with steamed broccoli and brown rice.",
                    "icon": "🍲"
                },
                {
                    "task_id": "task_7",
                    "time": "10:30 PM",
                    "period": "Bedtime",
                    "category": "sleep",
                    "title": "Restorative Circadian Sleep Routine",
                    "action": "Turn off screens, keep bedroom cool (19°C), and aim for 7.5 hours of sleep.",
                    "icon": "🌙"
                }
            ]
        },
        doctor_comments="Approved comprehensive renal care plan. Maintain daily hydration and avoid NSAIDs.",
        status="approved",
        doctor_name="Dr. Sarah Mitchell, MD",
        plan_id="cpl_demo_02"
    )

    # Pre-record 2 completed tasks for Robert Chen for today
    today_str = js._today_date_str()
    js.toggle_task_completion(
        patient_email="robert.chen@example.com",
        care_plan_id="cpl_demo_02",
        task_id="task_1",
        calendar_date=today_str,
        completed=True,
        category="hydration",
        title="Circadian Hydration & Electrolytes"
    )
    js.toggle_task_completion(
        patient_email="robert.chen@example.com",
        care_plan_id="cpl_demo_02",
        task_id="task_2",
        calendar_date=today_str,
        completed=True,
        category="exercise",
        title="Zone-2 Morning Walk (30 mins)"
    )

    logger.info("Demo seeding complete. Demo accounts ready.")
