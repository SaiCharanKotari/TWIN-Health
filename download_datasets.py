import urllib.request
import os

os.makedirs('datasets', exist_ok=True)

datasets = {
    'diabetes.csv': 'https://raw.githubusercontent.com/jbrownlee/Datasets/master/pima-indians-diabetes.data.csv',
    'heart_disease.csv': 'https://archive.ics.uci.edu/ml/machine-learning-databases/heart-disease/processed.cleveland.data',
    'liver_disease.csv': 'https://archive.ics.uci.edu/ml/machine-learning-databases/00225/Indian%20Liver%20Patient%20Dataset%20(ILPD).csv',
    'stroke.csv': 'https://raw.githubusercontent.com/georgemelrose/Patient-Level-Stroke-Prediction-Models/main/healthcare-dataset-stroke-data.csv',
    'ckd.csv': 'https://raw.githubusercontent.com/junaidqazi/DataSets_Practice_ScienceAcademy/master/chronic_kidney_disease.csv'
}

for name, url in datasets.items():
    try:
        print(f"Downloading {name}...")
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            with open(os.path.join('datasets', name), 'wb') as f:
                f.write(response.read())
        print(f"Successfully downloaded {name}")
    except Exception as e:
        print(f"Failed to download {name}: {e}")
