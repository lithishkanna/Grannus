"""
Controlled medical-symptom vocabulary + normalization.

Gemini is instructed to prefer these canonical names, but free-text input
(and small model drift) means we normalize defensively here too, so
downstream code (priority engine, dashboard grouping, analytics) can rely
on a closed set of symptom names rather than arbitrary strings.

This is intentionally a small, extensible starting set — add entries as
real transcripts surface new variants. Anything not recognized is kept
as-is (lightly cleaned) rather than dropped, so we never silently lose
patient-reported information.
"""
import re
from typing import Optional

# variant (lowercased, whitespace-normalized) -> canonical symptom name
SYMPTOM_VOCAB = {
    "head ache": "headache",
    "headache": "headache",
    "head pain": "headache",
    "fever": "fever",
    "high temperature": "fever",
    "body pain": "body pain",
    "body ache": "body pain",
    "bodyache": "body pain",
    "chest pain": "chest pain",
    "chest ache": "chest pain",
    "cold": "cold-like symptoms",
    "running nose": "cold-like symptoms",
    "runny nose": "cold-like symptoms",
    "sneezing": "cold-like symptoms",
    "cough": "cough",
    "dry cough": "cough",
    "wet cough": "cough",
    "breathing difficulty": "difficulty breathing",
    "difficulty breathing": "difficulty breathing",
    "shortness of breath": "difficulty breathing",
    "breathlessness": "difficulty breathing",
    "vomiting": "vomiting",
    "nausea": "nausea",
    "loose motion": "diarrhea",
    "loose motions": "diarrhea",
    "diarrhea": "diarrhea",
    "diarrhoea": "diarrhea",
    "stomach pain": "abdominal pain",
    "stomach ache": "abdominal pain",
    "abdominal pain": "abdominal pain",
    "hair loss": "hair loss",
    "hairfall": "hair loss",
    "hair fall": "hair loss",
    "weakness": "weakness",
    "fatigue": "fatigue",
    "tiredness": "fatigue",
    "dizziness": "dizziness",
    "giddiness": "dizziness",
    "loss of consciousness": "loss of consciousness",
    "fainting": "loss of consciousness",
    "bleeding": "bleeding",
    "heavy bleeding": "severe bleeding",
    "severe bleeding": "severe bleeding",
}

# Ambiguous colloquial terms that must NOT be auto-converted into a
# diagnosis. Map them to a safe, non-diagnostic description instead.
# ("சளி" -> "cold-like symptoms", never "common cold".)
AMBIGUOUS_TERMS = {
    "சளி": "cold-like symptoms",
    "cold-like symptoms": "cold-like symptoms",
}

BODY_LOCATIONS = {
    "head", "chest", "abdomen", "stomach", "back", "leg", "legs", "hand",
    "hands", "arm", "arms", "throat", "neck", "joint", "joints", "eye",
    "eyes", "ear", "ears",
}

_DURATION_RE = re.compile(
    r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>minute|hour|day|week|month)s?", re.IGNORECASE
)

_UNIT_MAP = {
    "minute": "minutes",
    "hour": "hours",
    "day": "days",
    "week": "weeks",
    "month": "months",
}


def is_known_symptom(raw: Optional[str]) -> bool:
    """True if `raw` maps to something already in the controlled vocabulary.

    Used to log vocabulary gaps (symptom terms Gemini produced that we don't
    recognize) so the vocabulary can be grown from real transcripts.
    """
    if not raw:
        return True
    key = re.sub(r"\s+", " ", raw.strip().lower())
    return key in AMBIGUOUS_TERMS or key in SYMPTOM_VOCAB


def normalize_symptom_name(raw: Optional[str]) -> Optional[str]:
    """Map a raw symptom phrase to the controlled vocabulary if possible.

    Never invents a diagnosis. Unknown terms are returned lightly cleaned
    (lowercased, trimmed) rather than dropped, so no patient-reported
    information is lost.
    """
    if not raw:
        return raw
    key = re.sub(r"\s+", " ", raw.strip().lower())
    if key in AMBIGUOUS_TERMS:
        return AMBIGUOUS_TERMS[key]
    if key in SYMPTOM_VOCAB:
        return SYMPTOM_VOCAB[key]
    return key


def normalize_body_location(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return raw
    return re.sub(r"\s+", " ", raw.strip().lower())


def parse_duration_text(raw: Optional[str]):
    """Best-effort parse of a free-text duration into (value, unit).

    Returns (None, None) if it can't be confidently parsed — callers should
    keep the raw text rather than guessing.
    """
    if not raw:
        return None, None
    match = _DURATION_RE.search(raw)
    if not match:
        return None, None
    value = float(match.group("value"))
    unit = _UNIT_MAP[match.group("unit").lower()]
    return value, unit
