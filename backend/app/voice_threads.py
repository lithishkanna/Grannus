"""
Two-way asynchronous voice threads for doctor-patient clinical communication.

Enables:
  - Doctor spoken English prescription / advice -> translated voice note for patient.
  - Patient spoken native language reply / query -> transcribed and translated to English for doctor.
  - Back-translation verification on every message to ensure clinical safety.
"""
import time
import uuid
import logging
from typing import Dict, List, Optional
from pydantic import BaseModel

from app.schemas import VoiceThread, VoiceThreadMessage

logger = logging.getLogger("rural_care.voice_threads")


class VoiceThreadManager:
    """Stores and coordinates asynchronous bilingual voice threads for telehealth consultations."""

    def __init__(self):
        self._threads: Dict[str, VoiceThread] = {}

    def get_or_create_thread(
        self,
        consultation_id: str,
        patient_language: str = "ta-IN",
        doctor_language: str = "en-IN",
    ) -> VoiceThread:
        """Fetch existing conversation thread or initialize new thread for consultation."""
        if consultation_id not in self._threads:
            thread_id = f"thread_{consultation_id[:8]}_{int(time.time())}"
            self._threads[consultation_id] = VoiceThread(
                thread_id=thread_id,
                consultation_id=consultation_id,
                patient_language=patient_language,
                doctor_language=doctor_language,
                messages=[],
            )
        return self._threads[consultation_id]

    def add_message(
        self,
        consultation_id: str,
        sender: str,
        original_text: str,
        translated_text: str,
        original_language: str,
        target_language: str,
        back_translated_text: Optional[str] = None,
        audio_base64: Optional[str] = None,
    ) -> VoiceThreadMessage:
        """Append a validated voice message with bilingual translation to the thread."""
        thread = self.get_or_create_thread(
            consultation_id=consultation_id,
            patient_language=target_language if sender == "doctor" else original_language,
            doctor_language=original_language if sender == "doctor" else target_language,
        )

        message_id = f"msg_{uuid.uuid4().hex[:8]}"
        created_at = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

        msg = VoiceThreadMessage(
            message_id=message_id,
            sender=sender,
            original_text=original_text,
            translated_text=translated_text,
            back_translated_text=back_translated_text,
            original_language=original_language,
            target_language=target_language,
            audio_base64=audio_base64,
            created_at=created_at,
        )
        thread.messages.append(msg)
        logger.info(
            "Appended voice thread message consultation_id=%s sender=%s msg_id=%s",
            consultation_id, sender, message_id
        )
        return msg

    def get_thread(self, consultation_id: str) -> Optional[VoiceThread]:
        return self._threads.get(consultation_id)


_thread_manager: Optional[VoiceThreadManager] = None


def get_voice_thread_manager() -> VoiceThreadManager:
    global _thread_manager
    if _thread_manager is None:
        _thread_manager = VoiceThreadManager()
    return _thread_manager
