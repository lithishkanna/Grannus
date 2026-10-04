"""
Safety / Red-flag Engine (Deterministic).

Evaluates patient input (structured summary, raw English transcript, original Indic
transcript, and acoustic biomarkers) for predefined red flags and safety conditions.
This process is deterministic and does not rely on downstream LLM judgement.
"""
import logging
import re
from typing import List, Optional, Set, Tuple

from app.schemas import (
    AcousticBiomarkerResult,
    SafetyRedFlag,
    SafetyScreening,
    Severity,
    StructuredMedicalSummary,
)

logger = logging.getLogger("rural_care.safety")

# Format: (keywords_to_match, requires_severe_flag, severity_output, action_output, reason_output)
RED_FLAG_RULES: List[Tuple[List[str], bool, str, str, str]] = [
    (["severe chest pain", "unbearable chest pain"], False, "critical", "emergency_referral", "Severe chest pain reported"),
    (["chest pain"], True, "critical", "emergency_referral", "Severe chest pain reported"),
    (["chest pain"], False, "high", "clinician_review", "Chest pain reported"),
    (["heart attack"], False, "critical", "emergency_referral", "Suspected heart attack reported"),

    (["difficulty breathing", "shortness of breath", "breathlessness", "can't breathe", "cannot breathe", "gasping", "choking", "chest tightness"], False, "critical", "emergency_referral", "Breathing difficulty reported"),

    (["blue lips", "cyanosis"], False, "critical", "emergency_referral", "Cyanosis / blue lips reported"),

    (["loss of consciousness", "fainting", "unconscious", "passed out", "blackout"], False, "critical", "emergency_referral", "Loss of consciousness reported"),

    (["severe bleeding", "heavy bleeding", "uncontrolled bleeding"], False, "critical", "emergency_referral", "Severe bleeding reported"),
    (["bleeding", "blood loss", "hemorrhage", "active bleeding"], False, "high", "clinician_review", "Bleeding reported"),

    # 0.9: "fits" matched with word boundaries via _matches_keyword
    (["seizure", "convulsion", "fits"], False, "critical", "emergency_referral", "Seizure or convulsions reported"),

    (["severe allergic reaction", "anaphylaxis"], False, "critical", "emergency_referral", "Severe allergic reaction reported"),
    (["allergic reaction"], True, "critical", "emergency_referral", "Severe allergic reaction reported"),

    (["high fever"], False, "high", "clinician_review", "High fever reported"),
    (["fever"], True, "high", "clinician_review", "High fever reported"),
    (["infant fever", "newborn fever", "baby fever"], False, "critical", "emergency_referral", "Infant fever reported"),
    (["fever with rash", "rash with fever"], False, "high", "clinician_review", "Fever with rash reported"),

    (["suicidal ideation", "self-harm", "suicide"], False, "critical", "emergency_referral", "Suicidal ideation or self-harm reported"),

    (["stroke", "slurred speech", "one-sided weakness", "sudden confusion"], False, "critical", "emergency_referral", "Potential stroke symptoms reported"),

    (["poisoning", "ingestion of harmful substance", "snakebite", "snake bite", "pesticide", "organophosphate", "insecticide", "rat poison"], False, "critical", "emergency_referral", "Poisoning or envenomation reported"),
    (["scorpion sting", "scorpion bite"], False, "critical", "emergency_referral", "Scorpion sting reported"),
    (["dog bite", "animal bite", "rabies"], False, "high", "clinician_review", "Animal bite reported"),

    (["severe burns", "burn injury", "electrical burn"], False, "critical", "emergency_referral", "Severe burns reported"),
    (["burns", "burn"], True, "high", "clinician_review", "Severe burns reported"),

    (["severe abdominal pain"], False, "high", "clinician_review", "Severe abdominal pain reported"),
    (["abdominal pain"], True, "high", "clinician_review", "Severe abdominal pain reported"),

    (["head injury", "head trauma", "skull fracture", "concussion"], False, "critical", "emergency_referral", "Head injury reported"),

    (["severe headache", "thunderclap", "worst headache"], False, "high", "clinician_review", "Severe headache reported"),
    (["headache"], True, "high", "clinician_review", "Severe headache reported"),

    (["vomiting blood", "blood in vomit", "vomited blood", "vomited and there was blood", "vomited and saw blood", "blood when vomiting", "blood while vomiting", "hematemesis", "blood in stool", "rectal bleeding", "blood in motions", "passing blood"], False, "high", "clinician_review", "Vomiting blood or gastrointestinal bleeding reported"),

    (["severe dehydration"], False, "high", "clinician_review", "Severe dehydration reported"),
    (["dehydration"], True, "high", "clinician_review", "Severe dehydration reported"),
    
    (["vaginal bleeding during pregnancy", "eclampsia", "pre-eclampsia", "labor pain", "water broke", "premature labor"], False, "critical", "emergency_referral", "Obstetric emergency reported"),
]

# 0.2: Indic keyword lists for Tamil, Hindi, Telugu, and transliterations
INDIC_RED_FLAG_RULES: List[Tuple[List[str], bool, str, str, str]] = [
    # Chest pain
    (
        [
            "மார்பு வலி", "நெஞ்சு வலி", "marbu vali", "nenju vali",
            "सीने में दर्द", "सीने में तेज दर्द", "छाती में दर्द", "छाती में तेज दर्द", "seene me dard", "chhati me dard",
            "ఛాతీ నొప్పి", "రొమ్ము నొప్పి", "chati noppi",
        ],
        False, "high", "clinician_review", "Chest pain reported (Indic)",
    ),
    (
        [
            "கடுமையான நெஞ்சு வலி", "கடுமையான மார்பு வலி",
            "सीने में तेज दर्द", "छाती में तेज दर्द", "छाती में भयंकर दर्द", "सीने में असहनीय दर्द",
            "తీవ్రమైన ఛాతీ నొప్పి",
        ],
        False, "critical", "emergency_referral", "Severe chest pain reported (Indic)",
    ),

    # Breathing difficulty
    (
        [
            "மூச்சு திணறல்", "மூச்சு விட சிரமம்", "மூச்சு வாங்க", "moochu thinaran", "moochu vida mudiyala",
            "सांस लेने में तकलीफ", "सांस फूलना", "दम घुटना", "saans lene me dikkat", "saans phoolna",
            "శ్వాస తీసుకోవడంలో ఇబ్బంది", "ఆయాసం", "swasa teeskolekapovadam", "aayasam",
        ],
        False, "critical", "emergency_referral", "Breathing difficulty reported (Indic)",
    ),

    # Loss of consciousness / fainting
    (
        [
            "மயக்கம்", "மயங்கி", "mayakkam", "mayangi",
            "बेहोश", "बेहोशी", "चक्कर खाकर गिर", "behoshi", "behosh",
            "స్పృహ తప్పడం", "కళ్లు తిరిగి పడిపోవడం", "spruha tappadam",
        ],
        False, "critical", "emergency_referral", "Loss of consciousness reported (Indic)",
    ),

    # Severe bleeding
    (
        [
            "அதிக ரத்தப்போக்கு", "ரத்தம் கொட்டுது", "athiga rathapokku",
            "खून बहना", "बहुत खून", "khoon behna", "bahut khoon",
            "తీవ్రమైన రక్తస్రావం", "raktasravam",
        ],
        False, "critical", "emergency_referral", "Severe bleeding reported (Indic)",
    ),

    # Bleeding (high)
    (
        [
            "ரத்தம்", "ரத்தப்போக்கு", "rathapokku", "ratham",
            "खून", "रक्त", "khoon behna", "khoon nikal", "khoon aana",
            "రక్తం", "రక్తస్రావం", "raktham",
        ],
        False, "high", "clinician_review", "Bleeding reported (Indic)",
    ),

    # Vomiting blood (high)
    (
        [
            "வாந்தியில் ரத்தம்", "ரத்த வாந்தி", "vaanthiyil ratham", "ratha vaanthi",
            "उल्टी में खून", "खून की उल्टी", "ulti me khoon", "khoon ki ulti",
            "వాంతిలో రక్తం", "రక్తం వాంతి", "vaanthilo raktham", "raktham vanthi",
        ],
        False, "high", "clinician_review", "Vomiting blood reported (Indic)",
    ),

    # Seizure / Fits
    (
        [
            "வலிப்பு", "ஜன்னி", "valippu", "janni",
            "दौरा", "मिर्गी", "झटके", "daura", "mirgi", "jhatke",
            "మూర్ఛ", "తీవ్రమైన వణుకు", "murcha",
        ],
        False, "critical", "emergency_referral", "Seizure or convulsions reported (Indic)",
    ),

    # Poisoning / Snakebite
    (
        [
            "விஷம்", "பாம்பு கடி", "visham", "pambu kadi",
            "जहर", "विष", "सांप काटना", "zeher", "vish", "saanp kaatna",
            "విషం", "పాము కాటు", "visham", "paamu kaatu",
        ],
        False, "critical", "emergency_referral", "Poisoning or snakebite reported (Indic)",
    ),

    # Stroke / Paralysis
    (
        [
            "பக்கவாதம்", "pakkavatham",
            "लकवा", "फालिज", "lakwa",
            "పక్షవాతం", "pakshavatam",
        ],
        False, "critical", "emergency_referral", "Potential stroke symptoms reported (Indic)",
    ),

    # Severe allergy
    (
        [
            "கடுமையான ஒவ்வாமை", "गंभीर एलर्जी", "తీవ్రమైన అలర్జీ",
        ],
        False, "critical", "emergency_referral", "Severe allergic reaction reported (Indic)",
    ),

    # Scorpion sting
    (
        [
            "தேள் கொட்டு", "thel kottu",
            "बिच्छू काटना", "bichhu katna",
            "తేలు కుట్టడం", "telu kuttadam",
        ],
        False, "critical", "emergency_referral", "Scorpion sting reported (Indic)",
    ),

    # Dog bite
    (
        [
            "நாய் கடி", "naai kadi",
            "कुत्ते का काटना", "kutte ka katna",
            "కుక్క కాటు", "kukka kaatu",
        ],
        False, "high", "clinician_review", "Animal bite reported (Indic)",
    ),

    # Burns
    (
        [
            "தீக்காயம்", "theekkayam",
            "जलना", "jalna",
            "కాలిన గాయం", "kaalina gaayam",
        ],
        True, "high", "clinician_review", "Severe burns reported (Indic)",
    ),

    # Head injury
    (
        [
            "தலையில் அடி", "thalaiyil adi",
            "सिर में चोट", "sir me chot",
            "తల గాయం", "tala gaayam",
        ],
        False, "critical", "emergency_referral", "Head injury reported (Indic)",
    ),

    # Obstetric
    (
        [
            "பிரசவ வலி", "prasava vali",
            "प्रसव पीड़ा", "prasav peeda",
            "ప్రసవ నొప్పులు", "prasava noppulu",
        ],
        False, "critical", "emergency_referral", "Obstetric emergency reported (Indic)",
    ),
]

_NEGATION_PATTERNS = [
    # English negations
    r"\b(?:no|not|don't|dont|does\s*not|doesn't|doesnt|didn't|didnt|did\s*not|denies|denied|without|never|haven't|havent|have\s*no|has\s*no|free\s*of)\b",
    # Indic negations (Tamil - Unicode script & transliterations with word boundaries)
    r"(?:^|[\s.,;!?|\n\r])(?:இல்லை|இல்ல|கிடையாது|\b(?:illai|illa|kidaiyathu)\b)(?:$|[\s.,;!?|\n\r])",
    # Indic negations (Hindi - Unicode script & transliterations with word boundaries to avoid 'ना' matching inside 'पसीना')
    r"(?:^|[\s.,;!?|\n\r])(?:नहीं|नही|ना|\b(?:nahi|nahin|na|mat)\b)(?:$|[\s.,;!?|\n\r])",
    # Indic negations (Telugu - Unicode script & transliterations with word boundaries)
    r"(?:^|[\s.,;!?|\n\r])(?:లేదు|కాదు|లేవు|\b(?:ledu|kadu|levu)\b)(?:$|[\s.,;!?|\n\r])",
]

# Delimiters that separate syntactic clauses (punctuation & contrastive conjunctions)
# Prevents negation bleeding across clauses (e.g. 'no fever, but severe chest pain')
_CLAUSE_DELIMITER_REGEX = re.compile(
    r"[.,;!?|\n\r]+|\b(?:but|however|except|yet|although|though|whereas|lekin|magar|parantu|kintu|aanaal|aanal|kaani|kani)\b",
    re.IGNORECASE,
)


def is_text_negated(text: str) -> bool:
    """Check if the text represents a negated symptom/phrase."""
    text_lower = text.lower()
    return any(re.search(pat, text_lower, re.IGNORECASE) for pat in _NEGATION_PATTERNS)


def is_negated_match(text: str, match_start: int, match_end: int) -> bool:
    """
    Check if the term matched at [match_start:match_end] in text is negated.
    Enforces strict clause boundary scoping so negations in one clause do not
    bleed into adjacent clauses (e.g., 'no fever, but chest pain').
    Checks up to 4 words before match_start and up to 3 words after match_end
    (essential for Indic SOV negation: 'nenju vali illa', 'dard nahi hai').
    """
    text_lower = text.lower()

    # 1. Preceding window within the immediate clause
    prefix = text_lower[:match_start]
    delimiters_before = list(_CLAUSE_DELIMITER_REGEX.finditer(prefix))
    if delimiters_before:
        last_delim = delimiters_before[-1]
        clause_prefix = prefix[last_delim.end():].strip()
    else:
        clause_prefix = prefix.strip()

    prefix_words = clause_prefix.split()
    preceding_window = " ".join(prefix_words[-4:]) if prefix_words else ""
    if preceding_window and any(re.search(pat, preceding_window, re.IGNORECASE) for pat in _NEGATION_PATTERNS):
        return True

    # 2. Following window within the immediate clause (Indic SOV: 'nenju vali illa')
    suffix = text_lower[match_end:]
    first_delim = _CLAUSE_DELIMITER_REGEX.search(suffix)
    if first_delim:
        clause_suffix = suffix[:first_delim.start()].strip()
    else:
        clause_suffix = suffix.strip()

    suffix_words = clause_suffix.split()
    following_window = " ".join(suffix_words[:3]) if suffix_words else ""
    if following_window and any(re.search(pat, following_window, re.IGNORECASE) for pat in _NEGATION_PATTERNS):
        return True

    return False


def _matches_keyword(keyword: str, text: str) -> List[Tuple[int, int]]:
    """
    Find occurrences of keyword in text using word boundaries for ASCII/alphanumeric keywords
    to prevent substring collisions like 'fits' in 'benefits' or 'fitness' (0.9).
    Returns list of (start_idx, end_idx) match spans.
    """
    spans: List[Tuple[int, int]] = []
    kw_clean = keyword.strip()
    if not kw_clean:
        return spans

    if kw_clean.isascii() and kw_clean.replace(" ", "").isalnum():
        pattern = rf"\b{re.escape(kw_clean)}\b"
    else:
        # Non-ASCII (Indic scripts) or phrases: match on character boundaries
        pattern = re.escape(kw_clean)

    for match in re.finditer(pattern, text, re.IGNORECASE):
        spans.append((match.start(), match.end()))
    return spans


def scan_raw_transcript(
    transcript_english: Optional[str] = None,
    transcript_original: Optional[str] = None,
) -> Tuple[List[SafetyRedFlag], bool, bool]:
    """
    0.2 Independent safety scan of raw English and original Indic transcripts.
    Returns:
        (detected_red_flags, has_chest_pain, has_breathing_info)
    """
    flags: List[SafetyRedFlag] = []
    has_chest_pain = False
    has_breathing_info = False

    def scan_text(text: str, rules: List[Tuple[List[str], bool, str, str, str]]):
        nonlocal has_chest_pain, has_breathing_info
        if not text:
            return
        text_lower = text.lower()

        # Check breathing info existence in text (even if negated, breathing was mentioned)
        if any(kw in text_lower for kw in [
            "breath", "breathing", "respiration", "shortness of breath", "breathless",
            "மூச்சு", "moochu", "सांस", "saans", "శ్వాస", "swasa", "ఆయాసం", "aayasam"
        ]):
            has_breathing_info = True

        for keywords, requires_severe, out_severity, out_action, out_reason in rules:
            for kw in keywords:
                spans = _matches_keyword(kw, text_lower)
                if not spans:
                    continue

                for start_idx, end_idx in spans:
                    if is_negated_match(text_lower, start_idx, end_idx):
                        logger.debug("Raw transcript match %r at pos %d is negated, skipping", kw, start_idx)
                        continue

                    # Non-negated chest pain match
                    if "chest pain" in out_reason.lower() or any(cp in kw.lower() for cp in [
                        "chest pain", "மார்பு வலி", "நெஞ்சு வலி", "marbu vali", "nenju vali",
                        "सीने", "छाती", "seene", "chhati", "ఛాతీ", "chati"
                    ]):
                        has_chest_pain = True

                    if requires_severe:
                        severe_cues = ["severe", "unbearable", "கடுமையான", "तेज", "भयंकर", "తీవ్రమైన"]
                        if not any(s in text_lower for s in severe_cues):
                            continue

                    flags.append(SafetyRedFlag(
                        potential_red_flag=True,
                        symptom=kw,
                        reason=out_reason,
                        action=out_action,
                        severity=out_severity,
                    ))
                    break  # Matched non-negated instance for this rule

    if transcript_english:
        scan_text(transcript_english, RED_FLAG_RULES)
    if transcript_original:
        scan_text(transcript_original, INDIC_RED_FLAG_RULES)
        # Also run English rules on original transcript for code-mixed speech
        scan_text(transcript_original, RED_FLAG_RULES)

    return flags, has_chest_pain, has_breathing_info


def screen_safety(
    summary: Optional[StructuredMedicalSummary] = None,
    biomarkers: Optional[AcousticBiomarkerResult] = None,
    transcript_english: Optional[str] = None,
    transcript_original: Optional[str] = None,
    language_code: Optional[str] = None,
) -> SafetyScreening:
    """
    Evaluates the structured medical summary and raw transcripts for predefined red flags.
    This process is deterministic and does not rely on LLM judgements.
    """
    logger.info("Starting deterministic safety screening")

    red_flags: List[SafetyRedFlag] = []
    missing_critical_info: List[str] = []

    has_chest_pain = False
    has_breathing_info = False

    def check_text_against_rules(text: str, is_severe: bool, source_symptom: str) -> None:
        """Helper to match text against defined red flag rules and generate safety flags."""
        text_lower = text.lower()
        matched_reasons: Set[str] = set()

        for keywords, requires_severe, out_severity, out_action, out_reason in RED_FLAG_RULES:
            if out_reason in matched_reasons:
                continue

            if requires_severe and not is_severe:
                continue

            matched = False
            for kw in keywords:
                spans = _matches_keyword(kw, text_lower)
                for start_idx, end_idx in spans:
                    if is_negated_match(text_lower, start_idx, end_idx):
                        continue
                    matched = True
                    break
                if matched:
                    break

            if matched:
                red_flags.append(SafetyRedFlag(
                    potential_red_flag=True,
                    symptom=source_symptom,
                    reason=out_reason,
                    action=out_action,
                    severity=out_severity,
                ))
                matched_reasons.add(out_reason)

    # 1. Process symptoms from structured summary
    has_sweating = False
    _SWEATING_TERMS = [
        "sweat", "sweating", "cold sweat", "profuse sweating", "diaphoresis", "perspiration",
        "पसीना", "pasina",
        "வேர்வை", "vervai", "வியர்வை",
        "చెమట", "chematalu", "chemata",
    ]

    if summary:
        if summary.chief_complaint:
            cc_lower = summary.chief_complaint.lower()
            if any(sw in cc_lower for sw in _SWEATING_TERMS) and not is_text_negated(cc_lower):
                has_sweating = True

        if summary.symptoms:
            for symptom in summary.symptoms:
                text_to_check = (symptom.name or "").lower()
                if symptom.raw_text:
                    text_to_check += f" {symptom.raw_text.lower()}"

                # 0.8: Breathing status is known if mentioned anywhere, even if negated
                if any(kw in text_to_check for kw in ["breath", "breathing", "respiration"]):
                    has_breathing_info = True

                # SKIP negated symptoms for active red flags
                if symptom.negated:
                    continue

                if any(sw in text_to_check for sw in _SWEATING_TERMS):
                    has_sweating = True

                is_severe = symptom.severity in (Severity.SEVERE, Severity.UNBEARABLE)
                check_text_against_rules(text_to_check, is_severe, symptom.name)

                if "chest pain" in text_to_check:
                    has_chest_pain = True

    # 2. Process Gemini-extracted red flags with negation check (0.8)
    if summary and summary.red_flags:
        for flag in summary.red_flags:
            text_to_check = flag.phrase.lower()

            # 0.8: Skip negated Gemini red flags (e.g. "no chest pain", "denies shortness of breath")
            if is_text_negated(text_to_check):
                logger.debug("Skipping negated Gemini red flag phrase: %s", flag.phrase)
                if any(kw in text_to_check for kw in ["breath", "breathing", "respiration"]):
                    has_breathing_info = True
                continue

            # Also check if related_symptom is marked negated in summary
            if flag.related_symptom and summary.symptoms:
                is_related_negated = any(
                    s.negated and s.name.lower() == flag.related_symptom.lower()
                    for s in summary.symptoms
                )
                if is_related_negated:
                    logger.debug("Skipping Gemini red flag because related symptom '%s' is negated", flag.related_symptom)
                    if any(kw in flag.related_symptom.lower() for kw in ["breath", "breathing", "respiration"]):
                        has_breathing_info = True
                    continue

            is_severe = "severe" in text_to_check or "unbearable" in text_to_check
            source_name = flag.related_symptom if flag.related_symptom else flag.phrase

            check_text_against_rules(text_to_check, is_severe, source_name)

            if "chest pain" in text_to_check:
                has_chest_pain = True
            if any(kw in text_to_check for kw in ["breath", "breathing", "respiration"]):
                has_breathing_info = True

    # 3. 0.2: Independent safety scan of raw transcripts
    if transcript_english or transcript_original:
        raw_flags, raw_chest_pain, raw_breathing_info = scan_raw_transcript(
            transcript_english=transcript_english,
            transcript_original=transcript_original,
        )
        red_flags.extend(raw_flags)
        has_chest_pain = has_chest_pain or raw_chest_pain
        has_breathing_info = has_breathing_info or raw_breathing_info

        # Scan raw transcripts for sweating
        for raw_t in [transcript_english, transcript_original]:
            if not raw_t:
                continue
            raw_t_lower = raw_t.lower()
            for sw in _SWEATING_TERMS:
                for start_idx, end_idx in _matches_keyword(sw, raw_t_lower):
                    if not is_negated_match(raw_t_lower, start_idx, end_idx):
                        has_sweating = True
                        break

    # 4. Deduplicate red flags
    unique_flags = []
    seen = set()
    for f in red_flags:
        key = (f.symptom.strip().lower(), f.reason.strip().lower(), f.severity.strip().lower())
        if key not in seen:
            seen.add(key)
            unique_flags.append(f)

    # Remove high flags if a critical flag exists for the SAME reason/symptom family
    final_flags = []
    for f in unique_flags:
        if f.severity == "high":
            has_critical = any(
                other.severity == "critical"
                and (
                    ("chest pain" in f.reason.lower() and "chest pain" in other.reason.lower())
                    or ("breathing" in f.reason.lower() and "breathing" in other.reason.lower())
                    or ("bleeding" in f.reason.lower() and "bleeding" in other.reason.lower())
                    or ("fever" in f.reason.lower() and "fever" in other.reason.lower())
                    or (f.symptom.lower() == other.symptom.lower())
                )
                for other in unique_flags
            )
            if has_critical:
                continue
        final_flags.append(f)

    # 5. 0.7: Add biomarker-driven flags: CAPPED at 'high' and strictly advisory
    if biomarkers:
        if biomarkers.respiratory_distress_score >= 0.6:
            final_flags.append(SafetyRedFlag(
                potential_red_flag=True,
                symptom="respiratory_distress_acoustic",
                reason="Respiratory distress detected from acoustic biomarker analysis (coughing/wheezing/breathlessness) [Advisory - Experimental]",
                action="clinician_review",
                severity="high",
            ))
        elif biomarkers.respiratory_distress_score >= 0.4:
            final_flags.append(SafetyRedFlag(
                potential_red_flag=True,
                symptom="respiratory_distress_acoustic",
                reason="Respiratory distress detected from acoustic biomarker analysis (coughing/wheezing/breathlessness) [Advisory - Experimental]",
                action="clinician_review",
                severity="moderate",
            ))

    # 6. 0.8: Missing critical info: chest pain with unknown breathing status
    if has_chest_pain and not has_breathing_info:
        missing_critical_info.append("Breathing status is unknown for patient with chest pain.")

    # 7. Override behavior: Only clinical/transcript critical red flags trigger emergency override
    has_critical_flags = any(
        f.severity == "critical" and f.symptom != "respiratory_distress_acoustic"
        for f in final_flags
    )
    override_priority = has_critical_flags

    return SafetyScreening(
        red_flags=final_flags,
        has_critical_flags=has_critical_flags,
        override_priority=override_priority,
        missing_critical_info=missing_critical_info,
        has_chest_pain=has_chest_pain,
        has_sweating=has_sweating,
    )
