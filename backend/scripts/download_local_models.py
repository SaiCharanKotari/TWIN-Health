import os
import shutil
from huggingface_hub import hf_hub_download

MODELS = [
    ("snehithakotakala/Diabetes_prediction", "knn_model.pkl", "diabetes", "space"),
    ("snehithakotakala/Diabetes_prediction", "scaler.pkl", "diabetes", "space"),
    ("abduleyo/heart-disease-classification-model", "model.joblib", "heart_disease", "model"),
    ("sanjana04/Chronic-kidney-disease-prediction", "logreg_model.pkl", "ckd", "space"),
    ("gianlab/model-liver-disease-prediction", "skops-xwel2v4p.pkl", "liver_disease", "model"),
    ("emlacodeuse/ml-stroke-prediction", "model.joblib", "stroke", "model")
]

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "models", "local")

def download_models():
    print(f"Downloading models to {BASE_DIR}...")
    
    for repo_id, filename, sub_dir, r_type in MODELS:
        target_dir = os.path.join(BASE_DIR, sub_dir)
        os.makedirs(target_dir, exist_ok=True)
        
        target_file = os.path.join(target_dir, filename)
        if os.path.exists(target_file):
            print(f"Already exists: {sub_dir}/{filename}")
            continue
            
        print(f"Downloading {filename} from {repo_id}...")
        try:
            cached_path = hf_hub_download(repo_id=repo_id, filename=filename, repo_type=r_type)
            shutil.copy2(cached_path, target_file)
            size_kb = os.path.getsize(target_file) / 1024
            print(f" -> Saved {sub_dir}/{filename} ({size_kb:.2f} KB)")
        except Exception as e:
            print(f" -> ERROR downloading {filename}: {e}")

if __name__ == "__main__":
    download_models()
