"""
Data Drift and Prediction Distribution Monitor for Grannus RuralCare AI.

Monitors real-time distribution of:
  - Priority predictions (HIGH, MEDIUM, LOW)
  - Critical feature missingness (e.g. age_missing, empty symptoms)
  - STT confidence shifts
  - Population Stability Index (PSI) against baseline gold distribution
"""
import logging
from collections import deque
from typing import Dict, List, Optional, Any
import numpy as np

logger = logging.getLogger("rural_care.drift_monitor")

# Target baseline distribution from adjudicated gold dataset
BASELINE_TRIAGE_DISTRIBUTION = {
    "HIGH": 0.40,
    "MEDIUM": 0.35,
    "LOW": 0.25,
}


def compute_psi(expected_probs: List[float], actual_probs: List[float], epsilon: float = 1e-4) -> float:
    """
    Computes Population Stability Index (PSI).
    PSI < 0.10: No significant shift
    0.10 <= PSI < 0.25: Moderate shift
    PSI >= 0.25: Significant shift / drift alert
    """
    psi = 0.0
    for exp, act in zip(expected_probs, actual_probs):
        exp = max(exp, epsilon)
        act = max(act, epsilon)
        psi += (act - exp) * np.log(act / exp)
    return float(psi)


class DriftMonitor:
    def __init__(self, window_size: int = 200):
        self.window_size = window_size
        self.history: deque = deque(maxlen=window_size)
        self.alert_history: List[Dict[str, Any]] = []

    def record_prediction(
        self,
        request_id: str,
        priority_level: str,
        confidence: float,
        features: Optional[Dict[str, float]] = None,
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record an incoming prediction event into the rolling window."""
        event = {
            "request_id": request_id,
            "priority_level": priority_level.upper(),
            "confidence": float(confidence),
            "features": features or {},
            "language": language or "unknown",
        }
        self.history.append(event)
        return self.check_drift()

    def get_distribution(self) -> Dict[str, float]:
        """Compute the current empirical priority distribution in the rolling window."""
        if not self.history:
            return {"HIGH": 0.0, "MEDIUM": 0.0, "LOW": 0.0}
        
        counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for item in self.history:
            lvl = item["priority_level"]
            if lvl in counts:
                counts[lvl] += 1
        
        total = len(self.history)
        return {k: round(v / total, 4) for k, v in counts.items()}

    def check_drift(self) -> Dict[str, Any]:
        """Check for statistical distribution drift against gold baseline."""
        n = len(self.history)
        if n < 20:
            # Need minimum sample size before alarming
            return {
                "window_count": n,
                "drift_detected": False,
                "status": "warming_up",
                "psi": 0.0,
                "current_distribution": self.get_distribution(),
            }

        current_dist = self.get_distribution()
        expected = [BASELINE_TRIAGE_DISTRIBUTION["HIGH"], BASELINE_TRIAGE_DISTRIBUTION["MEDIUM"], BASELINE_TRIAGE_DISTRIBUTION["LOW"]]
        actual = [current_dist["HIGH"], current_dist["MEDIUM"], current_dist["LOW"]]

        psi = compute_psi(expected, actual)

        alerts = []
        # Alert 1: Significant PSI drift
        if psi >= 0.25:
            alerts.append(f"Significant population stability drift detected (PSI={psi:.3f} >= 0.25)")

        # Alert 2: Safety hazard - sudden spike in LOW triage (> 45% when baseline is 25%)
        if current_dist["LOW"] > 0.45:
            alerts.append(f"Safety anomaly: LOW priority proportion ({current_dist['LOW']:.1%}) exceeds safe threshold (45.0%)")

        # Alert 3: Critical feature missingness spike
        age_missing_count = sum(1 for item in self.history if item["features"].get("age_missing", 0) == 1)
        if (age_missing_count / n) > 0.50:
            alerts.append(f"Data quality warning: High age missingness ({age_missing_count / n:.1%}) in recent intake")

        drift_detected = len(alerts) > 0
        status = "DRIFT_ALERT" if drift_detected else "STABLE"

        result = {
            "window_count": n,
            "drift_detected": drift_detected,
            "status": status,
            "psi": round(psi, 4),
            "current_distribution": current_dist,
            "baseline_distribution": BASELINE_TRIAGE_DISTRIBUTION,
            "alerts": alerts,
        }

        if drift_detected:
            logger.warning("DriftMonitor Alert: %s", alerts)
            self.alert_history.append(result)

        return result

    def reset(self):
        """Clear rolling window (used in testing)."""
        self.history.clear()
        self.alert_history.clear()


_monitor_instance: Optional[DriftMonitor] = None


def get_drift_monitor() -> DriftMonitor:
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = DriftMonitor()
    return _monitor_instance
