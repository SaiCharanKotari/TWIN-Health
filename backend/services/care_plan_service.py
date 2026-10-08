"""
backend/services/care_plan_service.py — Personalized Care Plan & Daily Lifestyle Intervention Engine.

Synthesizes:
1. Patient Demographics & Vitals
2. Multi-Disease Detection Risks (Diabetes, Heart, CKD, Liver, Stroke)
3. Underlying Biomarkers & Risk Drivers
4. Doctor / Clinician Commentary & Confirmation Notes

Outputs:
- Dietary Interventions (Foods to Eat, Foods to Avoid, Hydration, Meal Schedule with Timings)
- Exercise & Physical Regimen (Cardio, Strength, Mobility, Duration, Target Heart Rate, Timings)
- Vitamins & Micronutrients (Targeted supplements, Clinical Dosage, Intake Windows)
- 24-Hour Master Chronotherapy Schedule (Morning -> Midday -> Evening -> Night)
- Doctor Correlation & Medication Timing Principles
"""
from __future__ import annotations
import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
import google.generativeai as genai

from config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger("twinhealth.care_plan")

if GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here":
    try:
        genai.configure(api_key=GEMINI_API_KEY)
    except Exception as exc:
        logger.warning(f"Could not configure genai: {exc}")


async def generate_care_plan(
    patient_data: Dict[str, Any],
    disease_results: Dict[str, Any],
    doctor_comments: Optional[str] = "",
    uploaded_prescriptions: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Main entry point for generating the personalized daily care plan.
    Attempts Gemini Clinical AI first; falls back to Deterministic Clinical Decision Support (CDS) if needed.
    """
    # 1. Identify active disease risks & primary drivers
    risk_summary = _extract_risk_summary(disease_results)
    
    # 2. Attempt AI Generation
    ai_result = None
    if GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here":
        try:
            ai_result = await asyncio.wait_for(
                _generate_gemini_care_plan(patient_data, risk_summary, doctor_comments, uploaded_prescriptions),
                timeout=18.0
            )
        except Exception as exc:
            logger.warning(f"Gemini Care Plan generation failed/timed out: {exc}. Using Local Clinical CDS Engine.")

    if ai_result and isinstance(ai_result, dict) and "diet" in ai_result:
        ai_result["provider"] = "gemini-clinical-ai"
        return ai_result

    # 3. Deterministic Local Clinical CDS Engine Fallback
    local_plan = _generate_local_cds_care_plan(patient_data, risk_summary, doctor_comments, uploaded_prescriptions)
    local_plan["provider"] = "local-clinical-decision-support"
    return local_plan


def _extract_risk_summary(disease_results: Dict[str, Any]) -> Dict[str, Any]:
    """Summarizes detected diseases, probability, risk level, and drivers."""
    summary = {
        "high_risk": [],
        "moderate_risk": [],
        "low_risk": [],
        "key_drivers": [],
        "diseases": {}
    }
    
    for dis, data in disease_results.items():
        if not isinstance(data, dict):
            continue
        pred = data.get("prediction", {})
        label = (pred.get("label") or "unknown").lower()
        pct = pred.get("percentage") or (int(pred.get("probability", 0) * 100))
        name = data.get("display_name") or dis.replace("_", " ").title()
        
        info = {
            "disease": dis,
            "name": name,
            "percentage": pct,
            "label": label,
            "factors": data.get("explanation", {}).get("factors", [])
        }
        summary["diseases"][dis] = info
        
        if "high" in label or pct >= 65:
            summary["high_risk"].append(info)
        elif "mod" in label or pct >= 35:
            summary["moderate_risk"].append(info)
        else:
            summary["low_risk"].append(info)
            
        for f in info.get("factors", []):
            if f not in summary["key_drivers"]:
                summary["key_drivers"].append(f)
                
    return summary


async def _generate_gemini_care_plan(
    patient: Dict[str, Any],
    risks: Dict[str, Any],
    doctor_comments: Optional[str],
    uploaded_prescriptions: Optional[List[Dict[str, Any]]]
) -> Optional[Dict[str, Any]]:
    """Invokes Gemini to synthesize hyper-personalized care plan in strict JSON."""
    model_name = GEMINI_MODEL or "gemini-1.5-flash"
    clean_patient = {k: v for k, v in patient.items() if v is not None and v != ""}
    
    prompt = f"""You are an elite Clinical Nutritionist, Cardiometabolic Specialist, and Preventive Medicine Physician.
Create a comprehensive, personalized 24-hour Daily Life Changes & Medication Care Plan for this patient.

PATIENT PROFILE & BIOMARKERS:
{json.dumps(clean_patient, indent=2)}

DETECTED CHRONIC DISEASE RISKS:
High Risk Diseases: {[d['name'] + f" ({d['percentage']}%)" for d in risks.get('high_risk', [])]}
Moderate Risk Diseases: {[d['name'] + f" ({d['percentage']}%)" for d in risks.get('moderate_risk', [])]}
Key Biomarker Drivers: {risks.get('key_drivers', [])}

ATTENDING PHYSICIAN REMARKS:
"{doctor_comments or 'No physician comments provided. Follow evidence-based guidelines.'}"

UPLOADED / CURRENT MEDICATIONS:
{json.dumps(uploaded_prescriptions or [], indent=2)}

REQUIREMENTS:
Return a valid JSON object strictly matching this schema:
{{
  "title": "Personalized Cardiometabolic & Lifestyle Care Plan",
  "summary": "2-3 sentences summarizing clinical targets and strategy",
  "diet": {{
    "strategy_name": "e.g. Low-Glycemic Mediterranean-DASH Hybrid",
    "daily_hydration": "e.g. 2.5 - 3.0 Liters filtered water daily",
    "foods_to_eat": [
      {{"name": "Food item/group", "benefit": "Clinical rationale", "portion": "Recommended quantity"}}
    ],
    "foods_to_avoid": [
      {{"name": "Food item/group", "risk": "Why to avoid", "alternative": "Healthy swap"}}
    ],
    "meal_schedule": [
      {{"time": "08:30 AM", "meal": "Breakfast", "description": "Specific menu item", "glycemic_impact": "Low"}}
    ]
  }},
  "exercise": {{
    "regimen_name": "e.g. Zone-2 Aerobic & Insulin-Sensitizing Resistance Protocol",
    "weekly_goal_mins": 150,
    "daily_exercises": [
      {{"name": "Brisk Walking / Zone 2", "duration": "30 mins", "intensity": "Moderate (60-70% HR max)", "best_time": "07:00 AM or 45m post-dinner", "precautions": "Precaution note"}}
    ],
    "contraindications": ["Activity to avoid or limit"]
  }},
  "vitamins_and_supplements": [
    {{"name": "Vitamin / Micronutrient", "dosage": "e.g. 2000 IU", "timing": "e.g. Morning with breakfast", "rationale": "Evidence-based reason for this disease risk"}}
  ],
  "chronotherapy_schedule": [
    {{
      "time": "06:30 AM",
      "period": "Morning",
      "icon": "🌅",
      "title": "Wakeup & Hydration",
      "action": "500ml water with pinch of Himalayan pink salt",
      "category": "hydration"
    }},
    {{
      "time": "08:00 AM",
      "period": "Morning",
      "icon": "💊",
      "title": "Morning Medication & Vitamins",
      "action": "Take prescribed morning medications with breakfast",
      "category": "medication"
    }}
  ],
  "doctor_recommendations": "Specific actions aligned with physician remarks"
}}
"""
    model = genai.GenerativeModel(
        model_name=model_name,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.2,
            max_output_tokens=3000
        )
    )
    
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, lambda: model.generate_content(prompt))
    text = response.text.strip()
    return json.loads(text)


def _generate_local_cds_care_plan(
    patient: Dict[str, Any],
    risks: Dict[str, Any],
    doctor_comments: Optional[str],
    uploaded_prescriptions: Optional[List[Dict[str, Any]]]
) -> Dict[str, Any]:
    """
    Evidence-based Deterministic Clinical Decision Support (CDS) Plan Generator.
    Tailors recommendations using ADA (Diabetes), ACC/AHA (CVD/Stroke), KDIGO (CKD), and EASL (Liver) guidelines.
    """
    age = patient.get("age", 45)
    bmi = float(patient.get("bmi") or 26.0)
    high_diseases = [d["disease"] for d in risks.get("high_risk", [])]
    mod_diseases = [d["disease"] for d in risks.get("moderate_risk", [])]
    all_elevated = set(high_diseases + mod_diseases)
    
    # 1. Dietary Strategy
    foods_to_eat = []
    foods_to_avoid = []
    supplements = []
    daily_exercises = []
    
    has_diabetes = "diabetes" in all_elevated
    has_heart = "heart_disease" in all_elevated or "stroke" in all_elevated
    has_liver = "liver_disease" in all_elevated
    has_ckd = "ckd" in all_elevated
    
    # General Foundation
    foods_to_eat.append({
        "name": "Leafy Green Vegetables (Spinach, Kale, Fenugreek)",
        "benefit": "High magnesium, fiber, and antioxidant folate to lower endothelial inflammation.",
        "portion": "2 cups raw or 1 cup steamed daily"
    })
    foods_to_eat.append({
        "name": "Omega-3 Rich Seeds & Fish (Chia, Flaxseeds, Walnuts, Salmon)",
        "benefit": "Reduces systemic C-reactive protein, stabilizes plaque, improves lipid ratios.",
        "portion": "1-2 tablespoons ground seeds daily"
    })
    
    foods_to_avoid.append({
        "name": "Refined Sugars, Sweetened Beverages & Sodas",
        "risk": "Spikes postprandial glucose, accelerates de novo lipogenesis in liver and visceral fat accumulation.",
        "alternative": "Sparkling water with lemon, fresh mint, or Ceylon cinnamon tea"
    })
    foods_to_avoid.append({
        "name": "Deep-Fried Foods & Ultra-Processed Trans Fats",
        "risk": "Induces arterial stiffness, oxidative stress, and elevates LDL particle count.",
        "alternative": "Air-fried or oven-roasted vegetables in extra virgin olive oil"
    })

    # Disease-specific adjustments
    if has_diabetes:
        foods_to_eat.append({
            "name": "Low-Glycemic Legumes & Whole Grains (Lentils, Quinoa, Steel-cut Oats)",
            "benefit": "Slow beta-glucan digestion prevents glucose spikes and elevates GLP-1 sensitivity.",
            "portion": "1/2 to 3/4 cup per meal"
        })
        foods_to_avoid.append({
            "name": "White Bread, White Rice & Refined Flour (Maida)",
            "risk": "High glycemic index (>70) causes rapid insulin resistance and glucose volatility.",
            "alternative": "Ragi (finger millet), wild brown rice, or almond flour rotis"
        })
        supplements.append({
            "name": "Alpha-Lipoic Acid (ALA)",
            "dosage": "600 mg daily",
            "timing": "Morning 30 mins before breakfast",
            "rationale": "Clinical antioxidant that improves peripheral glucose disposal and protects against neuropathy."
        })
        supplements.append({
            "name": "Chromium Picolinate & Ceylon Cinnamon",
            "dosage": "200 mcg / 500 mg",
            "timing": "With main carbohydrate meal",
            "rationale": "Enhances insulin receptor signaling and stabilizes postprandial glucose."
        })

    if has_heart:
        foods_to_eat.append({
            "name": "Garlic, Berries & Nitrate-rich Beets",
            "benefit": "Stimulates endogenous nitric oxide (NO) production, lowering systolic BP by 4-8 mmHg.",
            "portion": "1 fresh crushed garlic clove + 1/2 cup fresh berries daily"
        })
        foods_to_avoid.append({
            "name": "High-Sodium Processed Meats & Packaged Snacks (>2,000 mg Na/day)",
            "risk": "Elevates intravascular volume, increasing arterial wall shear stress and stroke vulnerability.",
            "alternative": "Herbs, turmeric, potassium-rich potassium salt substitutes (if kidney function normal)"
        })
        supplements.append({
            "name": "Coenzyme Q10 (Ubiquinol)",
            "dosage": "100 - 200 mg daily",
            "timing": "Morning with dietary fat (breakfast)",
            "rationale": "Supports cardiac mitochondrial ATP synthesis, particularly if taking statins."
        })
        supplements.append({
            "name": "Magnesium Glycinate",
            "dosage": "300 - 400 mg daily",
            "timing": "Night, 45 minutes before sleep",
            "rationale": "Relaxes vascular smooth muscle tone, reduces blood pressure and arrhythmia risks."
        })

    if has_liver:
        foods_to_eat.append({
            "name": "Cruciferous Vegetables & Filtered Black Coffee (2-3 cups)",
            "benefit": "Induces Phase II liver detoxification enzymes (glutathione) and halts hepatic steatosis progression.",
            "portion": "1-2 cups broccoli/cabbage + 2 black coffees without sugar"
        })
        foods_to_avoid.append({
            "name": "High Fructose Corn Syrup & Alcoholic Beverages",
            "risk": "Directly drives hepatic triglyceride synthesis, steatohepatitis, and elevated ALT/AST.",
            "alternative": "Iced hibiscus tea, green tea with lemon"
        })
        supplements.append({
            "name": "Milk Thistle (Silymarin 80%) / NAC (N-Acetyl Cysteine)",
            "dosage": "250 mg Silymarin / 600 mg NAC",
            "timing": "Midday with lunch",
            "rationale": "Clinically shown to lower transaminases (ALT/AST) and enhance hepatic antioxidant defenses."
        })

    if has_ckd:
        foods_to_eat.append({
            "name": "Moderate Quality Plant Proteins (Tofu, Light Dhal)",
            "benefit": "Reduces glomerular hyperfiltration and nitrogenous waste accumulation compared to red meats.",
            "portion": "0.8g protein per kg bodyweight daily"
        })
        foods_to_avoid.append({
            "name": "Excessive Inorganic Phosphates & High Potassium Additives (Colas, processed meats)",
            "risk": "Overburdens damaged nephrons and accelerates decline in eGFR.",
            "alternative": "Home-cooked unpreserved whole foods"
        })

    # Universal Vitamin D3 + K2
    supplements.append({
        "name": "Vitamin D3 (Cholecalciferol) + K2 (MK-7)",
        "dosage": "2,000 - 5,000 IU D3 + 100 mcg K2",
        "timing": "Morning with breakfast",
        "rationale": "Essential for immunomodulation, vascular calcification prevention, and insulin sensitivity."
    })

    # Exercise Plan
    daily_exercises.append({
        "name": "Brisk Aerobic Walking / Incline Treadmill (Zone 2)",
        "duration": "35 - 45 mins",
        "intensity": "Moderate (Able to talk but not sing, 60-70% max HR)",
        "best_time": "07:00 AM (Fasted/Light Water) OR 30 mins after dinner",
        "precautions": "Maintain proper supportive athletic footwear and monitor hydration."
    })
    daily_exercises.append({
        "name": "Resistance / Bodyweight Muscle Activation (Squats, Wall Push-ups, Resistance Bands)",
        "duration": "20 - 25 mins",
        "intensity": "Moderate (3 sets of 10-12 reps with 60s rest)",
        "best_time": "05:30 PM (Pre-Dinner)",
        "precautions": "Avoid holding breath (Valsalva maneuver) to prevent sudden blood pressure spikes."
    })
    daily_exercises.append({
        "name": "Diaphragmatic Breathing & Postural Mobility",
        "duration": "10 mins",
        "intensity": "Restorative / Low",
        "best_time": "10:00 PM (Before Bed)",
        "precautions": "Slow 4-second inhale, 6-second exhale to downregulate sympathetic tone."
    })

    # Chronotherapy Master 24-Hour Schedule
    chronotherapy = [
        {
            "time": "06:30 AM",
            "period": "Early Morning",
            "icon": "🌅",
            "title": "Circadian Awakening & Cellular Hydration",
            "action": "Drink 500ml lukewarm filtered water with a slice of fresh lemon or pinch of rock salt.",
            "category": "hydration"
        },
        {
            "time": "07:00 AM",
            "period": "Morning",
            "icon": "🏃",
            "title": "Zone-2 Aerobic Exercise (35-45 mins)",
            "action": "Brisk outdoor walking or cycle ergometer. Gets natural morning light to synchronize melatonin rhythm.",
            "category": "exercise"
        },
        {
            "time": "08:15 AM",
            "period": "Morning",
            "icon": "💊",
            "title": "Morning Doctor Medications & Fat-Soluble Vitamins",
            "action": "Take doctor-prescribed morning medications + Vitamin D3/K2 & CoQ10 immediately with breakfast.",
            "category": "medication"
        },
        {
            "time": "08:30 AM",
            "period": "Morning",
            "icon": "🥗",
            "title": "Low-Glycemic Anti-Inflammatory Breakfast",
            "action": "Whole steel-cut oats with chia seeds, handful of walnuts, or 2 boiled eggs with steamed spinach.",
            "category": "diet"
        },
        {
            "time": "11:00 AM",
            "period": "Mid-Morning",
            "icon": "💧",
            "title": "Midday Hydration & Green Tea",
            "action": "Drink 350ml water + 1 cup unsweetened matcha or green tea (EGCG liver & vascular protection).",
            "category": "hydration"
        },
        {
            "time": "01:15 PM",
            "period": "Afternoon",
            "icon": "🍱",
            "title": "Balanced Cardiometabolic Lunch",
            "action": "Large salad bowl with olive oil, steamed legumes/grilled lean protein, and quinoa or millet.",
            "category": "diet"
        },
        {
            "time": "02:00 PM",
            "period": "Afternoon",
            "icon": "💊",
            "title": "Afternoon Medication (If Prescribed)",
            "action": "Take afternoon dose if scheduled by attending clinician.",
            "category": "medication"
        },
        {
            "time": "05:30 PM",
            "period": "Evening",
            "icon": "🏋️",
            "title": "Resistance Strength Training / Mobility",
            "action": "20 mins of resistance band or bodyweight exercises to stimulate GLUT4 glucose transporters.",
            "category": "exercise"
        },
        {
            "time": "07:30 PM",
            "period": "Dinner",
            "icon": "🍲",
            "title": "Light Early Dinner (At least 2.5h before bed)",
            "action": "Steamed vegetable soup, roasted tofu or lean lentils. Avoid all heavy carbs and deep-fried foods.",
            "category": "diet"
        },
        {
            "time": "09:00 PM",
            "period": "Night",
            "icon": "💊",
            "title": "Night Medications & Magnesium",
            "action": "Take prescribed night medications + Magnesium Glycinate for arterial relaxation and restorative sleep.",
            "category": "medication"
        },
        {
            "time": "10:30 PM",
            "period": "Bedtime",
            "icon": "🌙",
            "title": "Screen Off & 7-8 Hour Deep Restorative Sleep",
            "action": "Dark, cool bedroom (19-21°C). Sleep deprivation elevates morning cortisol and insulin resistance.",
            "category": "sleep"
        }
    ]

    summary_text = (
        f"Based on your patient profile and detected risk indicators "
        f"({', '.join([d['name'] for d in risks.get('high_risk', []) + risks.get('moderate_risk', [])]) or 'baseline wellness'}), "
        f"this clinical care plan prioritizes glycemic stabilization, endothelial vascular support, and hepatoprotective nutrition."
    )
    if doctor_comments:
        summary_text += f" Integrated with attending physician instructions: '{doctor_comments}'."

    return {
        "title": "Personalized Cardiometabolic & Daily Lifestyle Care Plan",
        "summary": summary_text,
        "active_risks": risks,
        "doctor_remarks": doctor_comments or "Clinical pre-screening guidelines applied.",
        "diet": {
            "strategy_name": "Cardiometabolic & Hepatic Protection Protocol",
            "daily_hydration": "2.5 to 3.0 Liters filtered water daily",
            "foods_to_eat": foods_to_eat,
            "foods_to_avoid": foods_to_avoid,
            "meal_schedule": [
                {"time": "08:30 AM", "meal": "Breakfast", "description": "High-fiber steel cut oats or boiled eggs with leafy greens", "glycemic_impact": "Low"},
                {"time": "01:15 PM", "meal": "Lunch", "description": "Colorful antioxidant salad with olive oil dressing + lentils/tofu", "glycemic_impact": "Low"},
                {"time": "05:00 PM", "meal": "Snack", "description": "Handful of raw almonds & walnuts with green tea", "glycemic_impact": "Zero"},
                {"time": "07:30 PM", "meal": "Dinner", "description": "Light vegetable stew or soup with steamed broccoli and seeds", "glycemic_impact": "Low"}
            ]
        },
        "exercise": {
            "regimen_name": "Zone-2 Aerobic & Insulin-Sensitizing Resistance Program",
            "weekly_goal_mins": 180,
            "daily_exercises": daily_exercises,
            "contraindications": [
                "Avoid sudden high-intensity bursts if resting BP > 140/90 mmHg without warm-up",
                "Avoid heavy dehydration; replenish electrolytes in warm conditions"
            ]
        },
        "vitamins_and_supplements": supplements,
        "chronotherapy_schedule": chronotherapy
    }
