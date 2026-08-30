"""
Central configuration. Reads secrets/settings from environment variables
(populated from .env via python-dotenv). Never hardcode API keys.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Sarvam AI ---
    sarvam_api_key: str = ""
    sarvam_stt_model: str = "saaras:v3"  # "saaras:v3" or "saaras:v4"
    sarvam_base_url: str = "https://api.sarvam.ai"
    sarvam_retry_attempts: int = 3
    sarvam_timeout_seconds: float = 30.0

    # --- Gemini ---
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"
    gemini_retry_attempts: int = 3
    gemini_timeout_seconds: float = 60.0

    # --- Audio Preprocessing ---
    enable_audio_preprocessing: bool = True
    min_audio_duration_seconds: float = 1.0
    max_audio_duration_seconds: float = 300.0  # 5 minutes
    target_sample_rate: int = 16000  # 16 kHz mono — what Sarvam accepts reliably
    noise_reduction_strength: float = 0.7  # 0.0 (none) to 1.0 (aggressive)

    # --- ML Model ---
    ml_model_path: str = "models/priority_model.joblib"
    ml_feature_columns_path: str = "models/feature_columns.json"
    ml_model_enabled: bool = True  # fall back to rule-based if False or model missing

    # --- App ---
    max_audio_bytes: int = 25 * 1024 * 1024  # 25 MB safety cap
    log_level: str = "INFO"

    # Below this, we don't trust the auto-detected language enough to rely
    # on the transcript without a doctor verifying it against the audio.
    language_confidence_threshold: float = 0.80


@lru_cache
def get_settings() -> Settings:
    """Cached singleton so we parse the .env file only once."""
    return Settings()
