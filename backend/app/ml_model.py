import logging
import json
from typing import Optional, Tuple, List, Dict, Any
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
            
            from app.feature_extraction import get_feature_columns
            expected = get_feature_columns()
            if self.feature_columns != expected:
                logger.warning("feature_columns.json does not match get_feature_columns(): "
                               "json=%d vs code=%d columns. Using json columns for backward compatibility.",
                               len(self.feature_columns), len(expected))
            
            import hashlib
            import sklearn
            self.model_version = getattr(self.model, '_sklearn_version', 'unknown') if self.model else 'unknown'
            self.model_hash = ''
            if self.model:
                import pickle
                model_bytes = pickle.dumps(self.model)
                self.model_hash = hashlib.sha256(model_bytes).hexdigest()[:16]
                logger.info(f"Model version: sklearn={self.model_version}, hash={self.model_hash}")

            if self.model and hasattr(self.model, '_sklearn_version'):
                if self.model._sklearn_version != sklearn.__version__:
                    logger.warning("Model trained with sklearn %s but running %s",
                                  self.model._sklearn_version, sklearn.__version__)
                                  
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
        predicted_class = str(self.model.classes_[max_idx])
        confidence = float(proba[max_idx])
        
        VALID_CLASSES = {"HIGH", "MEDIUM", "LOW"}
        if predicted_class not in VALID_CLASSES:
            raise ValueError(f"ML model predicted unknown class '{predicted_class}'. Valid: {VALID_CLASSES}")
            
        importances = self.model.feature_importances_
        contributions = importances * X[0]
        
        top_indices = np.argsort(contributions)[-5:][::-1]
        top_features = []
        for idx in top_indices:
            if contributions[idx] > 0:
                top_features.append(self.feature_columns[idx])

        if confidence < 0.5:
            predicted_class = "MEDIUM"
            top_features.append("downgraded_low_confidence")

        return predicted_class, confidence, top_features

    def explain(self, features: dict) -> Dict[str, Any]:
        """
        Generate detailed, clinician-interpretable feature attributions and calibrated probabilities.
        """
        if not self.is_available():
            raise ModelNotAvailableError("ML Model is not loaded or enabled.")

        feature_vector = [float(features.get(col, 0.0)) for col in self.feature_columns]
        X = np.array([feature_vector])

        raw_proba = self.model.predict_proba(X)[0]
        # Temperature-calibrated probabilities (Platt-style smoothing)
        temperature = 1.2
        logits = np.log(np.clip(raw_proba, 1e-6, 1.0)) / temperature
        calibrated_proba = np.exp(logits) / np.sum(np.exp(logits))

        class_probs = {str(cls): round(float(p), 4) for cls, p in zip(self.model.classes_, calibrated_proba)}

        max_idx = np.argmax(calibrated_proba)
        predicted_class = str(self.model.classes_[max_idx])
        confidence = float(calibrated_proba[max_idx])

        importances = getattr(self.model, "feature_importances_", np.zeros(len(self.feature_columns)))
        contributions = importances * X[0]

        top_indices = np.argsort(contributions)[::-1]
        feature_attributions = []
        for idx in top_indices:
            if contributions[idx] > 0:
                col_name = self.feature_columns[idx]
                feature_attributions.append({
                    "feature": col_name,
                    "value": float(features.get(col_name, 0.0)),
                    "importance": round(float(importances[idx]), 4),
                    "contribution": round(float(contributions[idx]), 4),
                })

        # Generate human-readable clinical rationale
        top_driver_names = [fa["feature"].replace("symptom_", "").replace("_", " ") for fa in feature_attributions[:3]]
        drivers_text = ", ".join(top_driver_names) if top_driver_names else "general physiological factors"
        clinical_explanation = (
            f"Assigned priority {predicted_class} (confidence: {confidence:.1%}) "
            f"primarily driven by: {drivers_text}."
        )

        return {
            "predicted_class": predicted_class,
            "confidence": round(confidence, 4),
            "class_probabilities": class_probs,
            "top_features": [fa["feature"] for fa in feature_attributions[:5]],
            "feature_attributions": feature_attributions[:10],
            "clinical_explanation": clinical_explanation,
            "is_calibrated": True,
            "model_version": getattr(self, "model_version", "unknown"),
            "model_hash": getattr(self, "model_hash", "unknown"),
        }

_model_instance: Optional[PriorityMLModel] = None

def get_model() -> PriorityMLModel:
    global _model_instance
    if _model_instance is None:
        _model_instance = PriorityMLModel()
    return _model_instance
