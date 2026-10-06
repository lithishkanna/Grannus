"""
Consent Architecture and Privacy Notice compliant with India's DPDP Act 2023.

Provides:
  - Multilingual consent notices in patient's native language
  - Explicit purpose limitation (triage & doctor consultation only)
  - Statutory Data Principal rights (Access, Correction, Erasure, Grievance Redressal)
  - Cryptographic timestamped consent record storage
"""
import time
import hashlib
from typing import Dict, Optional, List, Any
from pydantic import BaseModel, Field

CONSENT_VERSION = "2023.1-DPDP"

# Multilingual consent notices displayed before audio recording
CONSENT_NOTICES: Dict[str, Dict[str, str]] = {
    "en-IN": {
        "title": "Patient Consent & Privacy Notice (DPDP Act 2023)",
        "purpose": "Your voice recording will be used strictly to generate an AI clinical triage summary and assist your doctor. It will NOT be used for commercial advertising.",
        "retention": "Raw audio is automatically deleted within 24 hours. Medical summaries are retained securely for clinical follow-up.",
        "rights": "You have the right to withdraw consent, request access, or delete your health records at any time by contacting our Data Protection Grievance Officer.",
        "emergency_disclaimer": "Grannus is a decision support tool, NOT a definitive diagnosis. In medical emergencies, immediately call 108 or 112.",
        "checkbox_label": "I have understood the purpose and grant voluntary consent for voice recording.",
    },
    "ta-IN": {
        "title": "நோயாளி ஒப்புதல் மற்றும் தனியுரிமை அறிவிப்பு (DPDP சட்டம் 2023)",
        "purpose": "உங்கள் குரல் பதிவு மருத்துவரின் ஆலோசனைக்காகவும் அவசர உதவி சுருக்கம் தயாரிப்பதற்காகவும் மட்டுமே பயன்படுத்தப்படும். விளம்பரங்களுக்கு பயன்படுத்தப்படாது.",
        "retention": "குரல் பதிவு 24 மணி நேரத்திற்குள் தானாகவே நீக்கப்படும். மருத்துவ குறிப்புகள் பாதுகாப்பாக வைக்கப்படும்.",
        "rights": "உங்கள் மருத்துவ தரவுகளை நீக்கவோ அல்லது பார்வையிடவோ உங்களுக்கு முழு உரிமை உண்டு.",
        "emergency_disclaimer": "இது முடிவான சிகிச்சை அல்ல; மருத்துவ அவசரத்திற்கு உடனடியாக 108 அல்லது 112 ஐ அழைக்கவும்.",
        "checkbox_label": "நான் இந்த நோக்கத்தை புரிந்துகொண்டு குரல் பதிவு செய்ய முழு சம்மதம் தெரிவிக்கிறேன்.",
    },
    "hi-IN": {
        "title": "मरीज सहमति एवं गोपनीयता सूचना (DPDP अधिनियम 2023)",
        "purpose": "आपकी आवाज की रिकॉर्डिंग का उपयोग केवल डॉक्टर के परामर्श और प्राथमिक चिकित्सा सारांश के लिए किया जाएगा।",
        "retention": "ऑडियो रिकॉर्डिंग 24 घंटों के भीतर स्वतः हटा दी जाती है। मेडिकल सारांश सुरक्षित रखा जाता है।",
        "rights": "आपको कभी भी अपना डेटा देखने या हटाने का अनुरोध करने का पूरा अधिकार है।",
        "emergency_disclaimer": "यह अंतिम निदान नहीं है। किसी भी आपात स्थिति में तुरंत 108 या 112 पर कॉल करें।",
        "checkbox_label": "मैंने सभी नियम समझ लिए हैं और आवाज रिकॉर्डिंग के लिए अपनी सहमति देता/देती हूँ।",
    },
    "te-IN": {
        "title": "రోగి సమ్మతి మరియు గోప్యతా నోటీసు (DPDP చట్టం 2023)",
        "purpose": "మీ వాయిస్ రికార్డింగ్ డాక్టర్ సంప్రదింపుల కోసం మరియు అత్యవసర సారాంశం కోసం మాత్రమే ఉపయోగించబడుతుంది.",
        "retention": "వాయిస్ రికార్డింగ్ 24 గంటల్లో స్వయంచాలకంగా తొలగించబడుతుంది.",
        "rights": "మీ డేటాను ఎప్పుడైనా తొలగించే హక్కు మీకు ఉంది.",
        "emergency_disclaimer": "ఇది తుది వైద్య నిర్ధారణ కాదు. అత్యవసర పరిస్థితుల్లో వెంటనే 108 లేదా 112 కు కాల్ చేయండి.",
        "checkbox_label": "నేను ప్రయోజనాన్ని అర్థం చేసుకున్నాను మరియు వాయిస్ రికార్డింగ్ కోసం నా సమ్మతిని తెలియజేస్తున్నాను.",
    },
}

GRIEVANCE_OFFICER = {
    "name": "Data Protection Grievance Officer, Grannus Health",
    "email": "grievance.officer@grannus.health",
    "address": "Grannus Health Technologies India, Bengaluru, Karnataka",
    "statutory_reference": "Rule under Digital Personal Data Protection Act 2023",
}


class ConsentRecord(BaseModel):
    consent_id: str
    patient_id: str
    language_code: str
    consent_version: str = CONSENT_VERSION
    purpose: str
    timestamp: float = Field(default_factory=time.time)
    explicit_consent_granted: bool
    ip_hash: str
    retention_period_hours: int = 24


def get_consent_notice(language_code: str = "en-IN") -> Dict[str, Any]:
    """Retrieve localized consent notice."""
    notice = CONSENT_NOTICES.get(language_code, CONSENT_NOTICES["en-IN"])
    return {
        "version": CONSENT_VERSION,
        "language": language_code,
        "notice": notice,
        "grievance_officer": GRIEVANCE_OFFICER,
    }


def record_patient_consent(
    patient_id: str,
    language_code: str,
    client_ip: str,
    explicit_consent: bool,
) -> ConsentRecord:
    """Generate and store verified consent record."""
    if not explicit_consent:
        raise ValueError("Consent must be explicitly affirmed by the patient.")

    ip_hash = hashlib.sha256(client_ip.encode()).hexdigest()[:16]
    consent_id = f"CONSENT-{int(time.time())}-{ip_hash[:6]}"

    record = ConsentRecord(
        consent_id=consent_id,
        patient_id=patient_id,
        language_code=language_code,
        purpose="RuralCare AI Clinical Triage & Telemedicine Decision Support",
        explicit_consent_granted=True,
        ip_hash=ip_hash,
    )
    return record
