"""
TRAINED ON SYNTHETIC DATA - NOT FOR CLINICAL USE
"""
import sys
import os
import json
import numpy as np
import random
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score
import joblib

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.feature_extraction import get_feature_columns

def generate_synthetic_data(num_samples: int = 500):
    feature_cols = get_feature_columns()
    X = []
    y = []
    
    for _ in range(num_samples):
        features = {col: 0.0 for col in feature_cols}
        
        rand_val = random.random()
        # Edge cases (single chest pain)
        if rand_val > 0.95:
            features["symptom_chest_pain"] = 1.0
            features["max_severity"] = random.choice([3.0, 4.0])
            features["num_symptoms"] = 1.0
            y.append("MEDIUM" if features["max_severity"] == 3.0 else "HIGH")
        elif rand_val < 0.15:
            # Emergency cases
            features["symptom_chest_pain"] = 1.0
            features["symptom_difficulty_breathing"] = 1.0
            features["max_severity"] = random.choice([4.0, 5.0])
            features["num_symptoms"] = random.randint(2, 5)
            features["num_red_flags"] = random.randint(1, 3)
            features["has_continuous_symptom"] = 1.0
            y.append("HIGH")
        elif rand_val < 0.50:
            # Multi-symptom moderate cases
            features["symptom_fever"] = 1.0
            features["symptom_cough"] = 1.0
            features["symptom_body_pain"] = random.choice([0.0, 1.0])
            features["max_severity"] = random.choice([2.0, 3.0])
            features["num_symptoms"] = random.randint(2, 4)
            features["max_duration_days"] = random.uniform(1.0, 7.0)
            y.append("MEDIUM")
        else:
            # Single mild symptom cases
            features["symptom_headache"] = random.choice([0.0, 1.0])
            if not features["symptom_headache"]:
                features["symptom_cold_like_symptoms"] = 1.0
            features["max_severity"] = random.choice([1.0, 2.0])
            features["num_symptoms"] = 1.0
            features["max_duration_days"] = random.uniform(0.5, 3.0)
            y.append("LOW")
            
        features["age_group"] = float(random.randint(1, 4))
        if random.random() > 0.5:
            features["gender_male"] = 1.0
        else:
            features["gender_female"] = 1.0
            
        row = [features[col] for col in feature_cols]
        X.append(row)
        
    return np.array(X), np.array(y), feature_cols

def main():
    print("======================================================")
    print("TRAINED ON SYNTHETIC DATA — NOT FOR CLINICAL USE")
    print("======================================================")
    
    print("Generating synthetic data...")
    X, y, feature_cols = generate_synthetic_data(500)
    
    print("Training Random Forest...")
    clf = RandomForestClassifier(
        n_estimators=100,
        class_weight='balanced',
        random_state=42,
        max_depth=10
    )
    
    scores = cross_val_score(clf, X, y, cv=5)
    print(f"5-Fold CV Accuracy: {scores.mean():.3f} (+/- {scores.std() * 2:.3f})")
    
    clf.fit(X, y)
    
    models_dir = os.path.join(os.path.dirname(__file__), '..', 'models')
    os.makedirs(models_dir, exist_ok=True)
    
    model_path = os.path.join(models_dir, 'priority_model.joblib')
    features_path = os.path.join(models_dir, 'feature_columns.json')
    
    joblib.dump(clf, model_path)
    with open(features_path, 'w') as f:
        json.dump(feature_cols, f, indent=2)
        
    print(f"Saved model to {model_path}")
    print(f"Saved features to {features_path}")
    
    print("\nTop Feature Importances:")
    importances = clf.feature_importances_
    indices = np.argsort(importances)[::-1]
    for i in range(min(10, len(indices))):
        print(f"{i+1}. {feature_cols[indices[i]]} ({importances[indices[i]]:.4f})")

if __name__ == "__main__":
    main()
