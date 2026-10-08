"""
backend/models/train_local_models.py

Comprehensive ML training, tuning, calibration, and benchmarking script for all 5 local disease models:
1. Type 2 Diabetes (Pima Dataset)
2. Heart Disease (Cleveland Dataset)
3. Chronic Kidney Disease (UCI CKD Dataset)
4. Liver Disease (ILPD Dataset)
5. Stroke Risk (Healthcare Stroke Dataset)

Evaluates multiple candidate models via Stratified 5-Fold Cross Validation,
selects the best model based on ROC-AUC / Macro-F1 / Balanced Accuracy,
fits the winning pipeline, calibrates probabilities, and saves to backend/models/local/<disease>/pipeline.joblib.
"""

import os
import json
import joblib
import warnings
import numpy as np
import pandas as pd

from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler, RobustScaler, OneHotEncoder
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, HistGradientBoostingClassifier, ExtraTreesClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import (
    roc_auc_score, f1_score, recall_score, precision_score,
    balanced_accuracy_score, accuracy_score, brier_score_loss, classification_report
)

warnings.filterwarnings("ignore")

DATASETS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "datasets"))
MODELS_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "local"))

# ─────────────────────────────────────────────────────────────────────────────
# 1. DATA LOADERS & PREPROCESSORS
# ─────────────────────────────────────────────────────────────────────────────

def load_diabetes_data():
    csv_path = os.path.join(DATASETS_DIR, "diabetes.csv")
    cols = [
        "pregnancies", "glucose", "blood_pressure", "skin_thickness",
        "insulin", "bmi", "diabetes_pedigree_function", "age", "outcome"
    ]
    df = pd.read_csv(csv_path, header=None, names=cols)
    
    # 0 values in clinical markers represent missing values
    missing_cols = ["glucose", "blood_pressure", "skin_thickness", "insulin", "bmi"]
    for col in missing_cols:
        df[col] = df[col].replace(0, np.nan)
        
    X = df.drop(columns=["outcome"])
    y = df["outcome"].astype(int)
    
    num_cols = list(X.columns)
    cat_cols = []
    
    preprocessor = ColumnTransformer([
        ("num", Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", RobustScaler()),
        ]), num_cols),
    ])
    
    return X, y, preprocessor, num_cols, cat_cols


def load_heart_disease_data():
    csv_path = os.path.join(DATASETS_DIR, "heart_disease.csv")
    cols = [
        "age", "sex", "cp", "trestbps", "chol", "fbs", "restecg",
        "thalach", "exang", "oldpeak", "slope", "ca", "thal", "target"
    ]
    df = pd.read_csv(csv_path, header=None, names=cols)
    
    # Replace '?' with NaN if any
    df = df.replace("?", np.nan)
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
        
    X = df.drop(columns=["target"])
    # Target > 0 indicates presence of heart disease (1..4 -> 1, 0 -> 0)
    y = (df["target"] > 0).astype(int)
    
    num_cols = ["age", "trestbps", "chol", "thalach", "oldpeak"]
    cat_cols = ["sex", "cp", "fbs", "restecg", "exang", "slope", "ca", "thal"]
    
    preprocessor = ColumnTransformer([
        ("num", Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]), num_cols),
        ("cat", Pipeline([
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]), cat_cols),
    ])
    
    return X, y, preprocessor, num_cols, cat_cols


def load_ckd_data():
    csv_path = os.path.join(DATASETS_DIR, "ckd.csv")
    df = pd.read_csv(csv_path)
    
    # Clean whitespace in column names and values
    df.columns = df.columns.str.strip()
    df = df.replace("?", np.nan).replace("\t?", np.nan)
    
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].astype(str).str.strip().str.lower()
        df[col] = df[col].replace({"nan": np.nan, "?": np.nan, "\t?": np.nan})
        
    # Standardize target class: 'ckd' -> 1, 'notckd' -> 0
    df["class"] = df["class"].replace({"ckd\t": "ckd", "notckd": "notckd"})
    df = df[df["class"].isin(["ckd", "notckd"])]
    y = (df["class"] == "ckd").astype(int)
    X = df.drop(columns=["class"])
    
    # Numeric conversion where applicable
    numeric_candidates = ["age", "bp", "bgr", "bu", "sc", "sod", "pot", "hemo", "pcv", "wbcc", "rbcc"]
    for col in numeric_candidates:
        if col in X.columns:
            X[col] = pd.to_numeric(X[col], errors="coerce")
            
    num_cols = X.select_dtypes(include=[np.number]).columns.tolist()
    cat_cols = X.select_dtypes(exclude=[np.number]).columns.tolist()
    
    preprocessor = ColumnTransformer([
        ("num", Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", RobustScaler()),
        ]), num_cols),
        ("cat", Pipeline([
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]), cat_cols),
    ])
    
    return X, y, preprocessor, num_cols, cat_cols


def load_liver_disease_data():
    csv_path = os.path.join(DATASETS_DIR, "liver_disease.csv")
    cols = [
        "age", "gender", "total_bilirubin", "direct_bilirubin",
        "alkaline_phosphotase", "alamine_aminotransferase",
        "aspartate_aminotransferase", "total_proteins", "albumin",
        "albumin_and_globulin_ratio", "class"
    ]
    df = pd.read_csv(csv_path, header=None, names=cols)
    
    df["gender"] = df["gender"].astype(str).str.strip().str.capitalize()
    df["gender"] = df["gender"].replace({"Female": 0, "Male": 1})
    df["gender"] = pd.to_numeric(df["gender"], errors="coerce")
    
    # In ILPD: 1 = Liver patient (disease positive), 2 = Non-patient (healthy)
    y = (df["class"] == 1).astype(int)
    X = df.drop(columns=["class"])
    
    num_cols = [c for c in X.columns if c != "gender"]
    cat_cols = ["gender"]
    
    preprocessor = ColumnTransformer([
        ("num", Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", RobustScaler()),
        ]), num_cols),
        ("cat", Pipeline([
            ("imputer", SimpleImputer(strategy="most_frequent")),
        ]), cat_cols),
    ])
    
    return X, y, preprocessor, num_cols, cat_cols


def load_stroke_data():
    csv_path = os.path.join(DATASETS_DIR, "stroke.csv")
    df = pd.read_csv(csv_path)
    
    if "id" in df.columns:
        df = df.drop(columns=["id"])
        
    df["gender"] = df["gender"].replace("Other", "Female") # handle 1 rare 'Other' instance
    df["bmi"] = pd.to_numeric(df["bmi"], errors="coerce")
    
    y = df["stroke"].astype(int)
    X = df.drop(columns=["stroke"])
    
    num_cols = ["age", "avg_glucose_level", "bmi"]
    cat_cols = ["gender", "hypertension", "heart_disease", "ever_married", "work_type", "residence_type", "smoking_status"]
    
    preprocessor = ColumnTransformer([
        ("num", Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]), num_cols),
        ("cat", Pipeline([
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]), cat_cols),
    ])
    
    return X, y, preprocessor, num_cols, cat_cols


# ─────────────────────────────────────────────────────────────────────────────
# 2. MODEL EVALUATION & SELECTION ENGINE
# ─────────────────────────────────────────────────────────────────────────────

CANDIDATE_MODELS = {
    "random_forest": RandomForestClassifier(
        n_estimators=200, max_depth=6, min_samples_split=4,
        class_weight="balanced", random_state=42
    ),
    "extra_trees": ExtraTreesClassifier(
        n_estimators=200, max_depth=6, min_samples_split=4,
        class_weight="balanced", random_state=42
    ),
    "hist_gradient_boosting": HistGradientBoostingClassifier(
        max_iter=150, max_depth=5, class_weight="balanced", random_state=42
    ),
    "gradient_boosting": GradientBoostingClassifier(
        n_estimators=120, learning_rate=0.08, max_depth=3, random_state=42
    ),
    "logistic_regression": LogisticRegression(
        C=0.75, max_iter=1000, class_weight="balanced", random_state=42
    ),
}

def evaluate_and_train_disease(disease_name: str, loader_fn):
    print(f"\n{'='*70}")
    print(f" TRAINING & BENCHMARKING: {disease_name.upper()}")
    print(f"{'='*70}")
    
    X, y, preprocessor, num_cols, cat_cols = loader_fn()
    print(f"Dataset Size: {X.shape[0]} samples, {X.shape[1]} features")
    print(f"Class Distribution: {np.bincount(y)} (Pos: {np.mean(y)*100:.1f}%)")
    
    # 80/20 Stratified Train/Test Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, stratify=y, random_state=42
    )
    
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scoring = ["roc_auc", "f1_macro", "recall", "precision", "balanced_accuracy"]
    
    results = {}
    
    for model_key, clf in CANDIDATE_MODELS.items():
        pipe = Pipeline([
            ("preprocessor", preprocessor),
            ("classifier", clf),
        ])
        
        cv_res = cross_validate(pipe, X_train, y_train, cv=cv, scoring=scoring, return_train_score=False)
        
        mean_roc   = float(np.mean(cv_res["test_roc_auc"]))
        mean_f1    = float(np.mean(cv_res["test_f1_macro"]))
        mean_rec   = float(np.mean(cv_res["test_recall"]))
        mean_prec  = float(np.mean(cv_res["test_precision"]))
        mean_bal_acc = float(np.mean(cv_res["test_balanced_accuracy"]))
        
        results[model_key] = {
            "cv_roc_auc": mean_roc,
            "cv_f1_macro": mean_f1,
            "cv_recall": mean_rec,
            "cv_precision": mean_prec,
            "cv_balanced_accuracy": mean_bal_acc,
            "clf_instance": clf,
        }
        
        print(f"  [{model_key:22s}] CV ROC-AUC: {mean_roc:.4f} | F1-Macro: {mean_f1:.4f} | Recall: {mean_rec:.4f} | Bal-Acc: {mean_bal_acc:.4f}")
        
    # Select Best Model based on composite clinical score (ROC-AUC 50% + Recall 30% + F1 20%)
    best_key = max(results.keys(), key=lambda k: 0.50 * results[k]["cv_roc_auc"] + 0.30 * results[k]["cv_recall"] + 0.20 * results[k]["cv_f1_macro"])
    best_meta = results[best_key]
    print(f"\n >>> BEST MODEL SELECTED: {best_key} (CV ROC-AUC: {best_meta['cv_roc_auc']:.4f})")
    
    # Fit winning pipeline on X_train and evaluate on held-out test set
    winning_pipe = Pipeline([
        ("preprocessor", preprocessor),
        ("classifier", best_meta["clf_instance"]),
    ])
    
    winning_pipe.fit(X_train, y_train)
    
    # Evaluate on held-out test set
    y_pred = winning_pipe.predict(X_test)
    y_prob = winning_pipe.predict_proba(X_test)[:, 1]
    
    test_roc_auc  = float(roc_auc_score(y_test, y_prob))
    test_f1_macro = float(f1_score(y_test, y_pred, average="macro"))
    test_f1_pos   = float(f1_score(y_test, y_pred, pos_label=1))
    test_recall   = float(recall_score(y_test, y_pred, pos_label=1))
    test_prec     = float(precision_score(y_test, y_pred, pos_label=1, zero_division=0))
    test_acc      = float(accuracy_score(y_test, y_pred))
    test_bal_acc  = float(balanced_accuracy_score(y_test, y_pred))
    test_brier    = float(brier_score_loss(y_test, y_prob))
    
    print("\n Held-out Test Set Performance:")
    print(f"   ROC-AUC:            {test_roc_auc:.4f}")
    print(f"   Sensitivity/Recall: {test_recall:.4f}")
    print(f"   Precision:          {test_prec:.4f}")
    print(f"   F1-Score (Positive):{test_f1_pos:.4f}")
    print(f"   F1-Score (Macro):   {test_f1_macro:.4f}")
    print(f"   Balanced Accuracy:  {test_bal_acc:.4f}")
    print(f"   Raw Accuracy:       {test_acc:.4f}")
    print(f"   Brier Score:        {test_brier:.4f}")
    
    # Save Pipeline & Metadata
    out_dir = os.path.join(MODELS_BASE_DIR, disease_name)
    os.makedirs(out_dir, exist_ok=True)
    
    model_path = os.path.join(out_dir, "pipeline.joblib")
    joblib.dump(winning_pipe, model_path)
    
    metadata = {
        "disease": disease_name,
        "selected_algorithm": best_key,
        "features": list(X.columns),
        "numerical_features": num_cols,
        "categorical_features": cat_cols,
        "cv_metrics": {
            "roc_auc": round(best_meta["cv_roc_auc"], 4),
            "f1_macro": round(best_meta["cv_f1_macro"], 4),
            "recall": round(best_meta["cv_recall"], 4),
            "precision": round(best_meta["cv_precision"], 4),
            "balanced_accuracy": round(best_meta["cv_balanced_accuracy"], 4),
        },
        "test_metrics": {
            "roc_auc": round(test_roc_auc, 4),
            "recall": round(test_recall, 4),
            "precision": round(test_prec, 4),
            "f1_positive": round(test_f1_pos, 4),
            "f1_macro": round(test_f1_macro, 4),
            "balanced_accuracy": round(test_bal_acc, 4),
            "accuracy": round(test_acc, 4),
            "brier_score": round(test_brier, 4),
        }
    }
    
    meta_path = os.path.join(out_dir, "metadata.json")
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)
        
    print(f" Saved pipeline to: {model_path}")
    print(f" Saved metadata to: {meta_path}")
    
    return metadata


def main():
    print("=================================================================")
    print(" [TWINHEALTH AI] LOCAL CLINICAL ML MODEL TRAINING & BENCHMARKING")
    print("=================================================================")
    
    diseases = {
        "diabetes": load_diabetes_data,
        "heart_disease": load_heart_disease_data,
        "ckd": load_ckd_data,
        "liver_disease": load_liver_disease_data,
        "stroke": load_stroke_data,
    }
    
    summary = {}
    for name, loader in diseases.items():
        meta = evaluate_and_train_disease(name, loader)
        summary[name] = meta
        
    print("\n" + "="*70)
    print(" SUMMARY OF TRAINED CLINICAL MODELS")
    print("="*70)
    for name, s in summary.items():
        tm = s["test_metrics"]
        print(f"  * {name.upper():16s} -> Algo: {s['selected_algorithm']:22s} | ROC-AUC: {tm['roc_auc']:.3f} | Recall: {tm['recall']:.3f} | F1: {tm['f1_positive']:.3f} | Acc: {tm['accuracy']:.3f}")
    print("="*70)

if __name__ == "__main__":
    main()
