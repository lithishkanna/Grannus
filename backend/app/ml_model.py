import logging
import json
from typing import Optional, Tuple, List
import numpy as np
import joblib

from app.config import get_settings

logger = logging.getLogger("rural_care.ml_model")

class ModelNotAvailableError(Exception):
    pass

class PriorityMLModel:
    def __init__(self):
        settings = get_settings()
        self.model = None
        self.feature_columns = []
        
        if not settings.ml_model_enabled:
            logger.info("ML model is disabled via config.")
            return

        try:
            self.model = joblib.load(settings.ml_model_path)
            with open(settings.ml_feature_columns_path, "r") as f:
                self.feature_columns = json.load(f)
            logger.info(f"Loaded ML model from {settings.ml_model_path}")
        except Exception as e:
            logger.warning(f"Could not load ML model from {settings.ml_model_path}: {e}")
            self.model = None

    def is_available(self) -> bool:
        return self.model is not None

    def predict(self, features: dict) -> Tuple[str, float, List[str]]:
        if not self.is_available():
            raise ModelNotAvailableError("ML Model is not loaded or enabled.")

        feature_vector = []
        for col in self.feature_columns:
            feature_vector.append(float(features.get(col, 0.0)))
            
        X = np.array([feature_vector])
        
        proba = self.model.predict_proba(X)[0]
        
        max_idx = np.argmax(proba)
        predicted_class = self.model.classes_[max_idx]
        confidence = proba[max_idx]
        
        importances = self.model.feature_importances_
        contributions = importances * X[0]
        
        top_indices = np.argsort(contributions)[-5:][::-1]
        top_features = []
        for idx in top_indices:
            if contributions[idx] > 0:
                top_features.append(self.feature_columns[idx])

        return str(predicted_class), float(confidence), top_features

_model_instance: Optional[PriorityMLModel] = None

def get_model() -> PriorityMLModel:
    global _model_instance
    if _model_instance is None:
        _model_instance = PriorityMLModel()
    return _model_instance
