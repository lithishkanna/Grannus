"""
Reference Home Remedy Library for RuralCare AI (Grannus).

Educational self-care information for mild, self-limiting
rural health complaints (Tier 4: Self-Care). Synthetic demonstration library.

Strict Safety Invariant: Every remedy MUST carry explicit 'See a Doctor If' red-flag criteria.
Does not replace clinician advice.
"""
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from app.schemas import HomeRemedyGuidance, HomeRemedyCareStep


class ApprovedRemedy(BaseModel):
    remedy_id: str
    title: str
    symptom_keywords: List[str]
    care_steps: List[str]
    monitoring_signs: List[str]
    seek_doctor_if: List[str]
    translations: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


# Small, clinically approved library of home care protocols
APPROVED_REMEDY_LIBRARY: Dict[str, ApprovedRemedy] = {
    "mild_cough_cold": ApprovedRemedy(
        remedy_id="mild_cough_cold",
        title="Mild Cough & Upper Respiratory Care",
        symptom_keywords=[
            "cough", "cold", "runny nose", "sneezing", "sore throat", "mild fever", "nasal congestion",
            "இருமல்", "சளி", "மூக்கு ஒழுகுதல்", "தொண்டை வலி",
            "खांसी", "जुकाम", "सर्दी", "गले में खराश",
            "దగ్గు", "జలుబు", "గొంతు నొప్పి",
        ],
        care_steps=[
            "Steam inhalation with clean plain warm water for 5 to 10 minutes twice daily.",
            "Warm saline water gargling (1/2 teaspoon common salt in 1 cup warm boiled water) 3 times a day for throat soothing.",
            "Drink plenty of warm boiled water, herbal ginger/tulsi infusion, or warm clear broth throughout the day.",
            "Take adequate bed rest in a well-ventilated room and sleep with head slightly elevated.",
            "Avoid cold drinks, direct cold air drafts, and exposure to cooking smoke or dust.",
        ],
        monitoring_signs=[
            "Fever rising above 101°F (38.3°C) or lasting more than 3 consecutive days.",
            "Increasing frequency or severity of coughing episodes.",
            "Onset of mild throat tightness or reduced oral fluid intake.",
        ],
        seek_doctor_if=[
            "Any difficulty breathing, shortness of breath, or wheezing/whistling sounds while breathing.",
            "Severe persistent chest tightness or chest pain.",
            "Coughing up blood or thick rust-colored phlegm.",
            "High fever with chills that does not respond to resting.",
            "Extreme weakness, inability to drink liquids, or symptoms worsening after 3 days.",
        ],
        translations={
            "ta-IN": {
                "care_steps": [
                    "சுத்தமான வெந்நீரில் தினமும் இருமுறை 5 முதல் 10 நிமிடங்கள் ஆவி பிடிக்கவும்.",
                    "தொண்டை வலிக்கு ஒரு டம்ளர் வெதுவெதுப்பான நீரில் அரை ஸ்பூன் உப்பு கலந்து தினமும் மூன்று முறை கொப்பளிக்கவும்.",
                    "சுடவைத்து ஆறிய வெந்நீர், சுக்கு மல்லி காபி அல்லது துளசி கஷாயம் அதிகம் பருகவும்.",
                    "நன்கு காற்றோட்டமான அறையில் போதுமான ஓய்வு எடுக்கவும்.",
                ],
                "seek_doctor_if": [
                    "மூச்சு விடுவதில் சிரமம் அல்லது மூச்சு திணறல் ஏற்பட்டால்.",
                    "கடுமையான நெஞ்சு வலி அல்லது மார்பு பகுதியில் பாரம் இருந்தால்.",
                    "இருமும்போது ரத்தம் அல்லது அடர் நிற சளி வந்தால்.",
                    "3 நாட்களுக்கு மேல் காய்ச்சல் நீடித்தால் உடனே மருத்துவரை அணுகவும்.",
                ],
            },
            "hi-IN": {
                "care_steps": [
                    "दिन में दो बार 5 से 10 मिनट के लिए गर्म पानी की भाप लें।",
                    "गले की राहत के लिए गुनगुने पानी में आधा चम्मच नमक डालकर दिन में 3 बार गरारे करें।",
                    "गुनगुना उबला पानी, तुलसी-अदरक का काढ़ा या हल्का सूप भरपूर मात्रा में पिएं।",
                    "हवादार कमरे में पूरा आराम करें और सिर को थोड़ा ऊंचा रखकर सोएं।",
                ],
                "seek_doctor_if": [
                    "सांस लेने में किसी भी तरह की तकलीफ या सीने में जकड़न हो।",
                    "खांसी में खून या अत्यधिक गाढ़ा बलगम आना।",
                    "3 दिन से अधिक समय तक तेज बुखार बना रहना।",
                    "अत्यधिक कमजोरी महसूस होना या पानी भी न पी पाना।",
                ],
            },
            "te-IN": {
                "care_steps": [
                    "రోజుకు రెండుసార్లు 5-10 నిమిషాలు వేడి నీటి ఆవిరి పట్టండి.",
                    "గొంతు నొప్పి ఉపశమనం కోసం గోరువెచ్చని నీటిలో చిటికెడు ఉప్పు వేసి రోజుకు 3 సార్లు పుక్కిలించండి.",
                    "గోరువెచ్చని కాచి చల్లార్చిన నీరు, తులసి-అల్లం కషాయం లేదా ద్రవాహారం ఎక్కువగా తీసుకోండి.",
                    "గాలి వెలుతురు ఉన్న గదిలో తగినంత విశ్రాంతి తీసుకోండి.",
                ],
                "seek_doctor_if": [
                    "శ్వాస తీసుకోవడంలో ఇబ్బంది లేదా ఆయాసం రావడం.",
                    "దగ్గులో రక్తం పడటం లేదా తీవ్రమైన ఛాతీ నొప్పి రావడం.",
                    "3 రోజుల కంటే ఎక్కువ కాలం తీవ్ర జ్వరం కొనసాగడం.",
                    "నీరు కూడా తాగలేనంత నీరసం రావడం.",
                ],
            },
        },
    ),
    "mild_diarrhea_vomiting": ApprovedRemedy(
        remedy_id="mild_diarrhea_vomiting",
        title="Oral Rehydration for Mild Diarrhea & Upset Stomach",
        symptom_keywords=[
            "loose stool", "diarrhea", "vomiting", "watery stool", "stomach upset", "loose motion",
            "வயிற்றுப்போக்கு", "வாந்தி", "வயிறு உப்புசம்",
            "दस्त", "उल्टी", "पेट खराब", "पतले दस्त",
            "విరేచనాలు", "వాంతులు", "కడుపు నొప్పి",
        ],
        care_steps=[
            "Prepare WHO Oral Rehydration Solution (ORS): Dissolve 1 sachet in exactly 1 litre of clean boiled and cooled drinking water.",
            "Drink 1 cup of prepared ORS solution in small, frequent sips after each loose bowel movement (1/2 cup for children).",
            "Supplement with clean home fluids: tender coconut water, diluted salted buttermilk (chaas), and light rice kanji with salt.",
            "Eat light, easily digestible foods like plain khichdi, banana, and curd rice in small portions; avoid fasting.",
            "Avoid milk products (except curd/buttermilk), oily, spicy, raw, or sugary street food.",
        ],
        monitoring_signs=[
            "Signs of progressive dehydration: dry sticky mouth, sunken eyes, unusual thirst, decreased urine output (< 3 times/day).",
            "Persistent nausea or lightheadedness when sitting up.",
        ],
        seek_doctor_if=[
            "Any blood or black tarry material in the stool or vomit.",
            "Continuous vomiting preventing you from keeping any fluids down for more than 4 hours.",
            "Severe sunken eyes, lethargy, confusion, or unable to pass urine for over 6 hours.",
            "High fever (> 101°F) accompanied by intense abdominal cramping.",
            "Diarrhea continuing beyond 48 hours without improvement.",
        ],
        translations={
            "ta-IN": {
                "care_steps": [
                    "WHO ஓ.ஆர்.எஸ் (ORS) பொடியை 1 லிட்டர் காய்ச்சி ஆறிய சுத்தமான தண்ணீரில் கலந்து வைத்துக்கொள்ளவும்.",
                    "ஒவ்வொரு முறை மலம் கழித்த பிறகும் ஒரு டம்ளர் ஓ.ஆர்.எஸ் கரைசலை சிறிது சிறிதாக குடிக்கவும்.",
                    "இளநீர், மோர், உப்பிட்ட கஞ்சி போன்ற நீர் ஆகாரங்களை அடிக்கடி பருகவும்.",
                    "எண்ணெய், காரமான உணவுகளை தவிர்த்து தயிர் சாதம், இட்லி போன்ற எளிய உணவுகளை உண்ணவும்.",
                ],
                "seek_doctor_if": [
                    "மலத்தில் ரத்தம் அல்லது கருப்பு நிற மலம் வெளியேறினால்.",
                    "தொடர் வாந்தியால் தண்ணீர் கூட குடிக்க முடியாமல் போனால்.",
                    "6 மணி நேரத்திற்கு மேல் சிறுநீர் வராமல் இருப்பது, நாக்கு வறண்டு போதல் போன்ற தீவிர நீர்ச்சத்து இழப்பு அறிகுறிகள் இருந்தால்.",
                    "2 நாட்களுக்கு மேல் வயிற்றுப்போக்கு நிற்கவில்லை என்றால் உடனே மருத்துவமனைக்கு செல்லவும்.",
                ],
            },
            "hi-IN": {
                "care_steps": [
                    "ओआरएस (ORS) का 1 पैकेट 1 लीटर उबले और ठंडे किए गए साफ पानी में अच्छी तरह घोलें।",
                    "हर बार पतले दस्त के बाद एक गिलास ओआरएस का घोल घूंट-घूंट करके पिएं।",
                    "नारियल पानी, नमकीन छाछ और चावल की पतली कांजी का सेवन करें।",
                    "हल्का और सुपाच्य भोजन जैसे खिचड़ी, केला और दही-चावल खाएं। तला-भुना बिल्कुल न खाएं।",
                ],
                "seek_doctor_if": [
                    "मल या उल्टी में खून आना।",
                    "लगातार उल्टी होना जिससे पानी भी अंदर न रुक पाए।",
                    "6 घंटे से पेशाब न होना, अत्यधिक सूखा मुंह या बेहोशी जैसे निर्जलीकरण के लक्षण।",
                    "48 घंटे बाद भी दस्त ठीक न होना।",
                ],
            },
            "te-IN": {
                "care_steps": [
                    "ఒక లీటరు కాచి చల్లార్చిన నీటిలో ఒక ప్యాకెట్ ఓఆర్ఎస్ (ORS) పొడిని కలపండి.",
                    "ప్రతిసారి విరేచనం అయిన తర్వాత ఒక గ్లాసు ఓఆర్ఎస్ ద్రావణాన్ని కొద్దికొద్దిగా తాగండి.",
                    "కొబ్బరి నీళ్లు, ఉప్పు కలిపిన మజ్జిగ, గంజి వంటి ద్రవాలు పుష్కలంగా తీసుకోండి.",
                    "కిచిడీ, పెరుగన్నం వంటి తేలికపాటి ఆహారం తినండి.",
                ],
                "seek_doctor_if": [
                    "మలంలో లేదా వాంతిలో రక్తం కనిపించడం.",
                    "నీరు కూడా ఆగకుండా వరుసగా వాంతులు కావడం.",
                    "6 గంటలకు పైగా మూత్రం రాకపోవడం లేదా తీవ్రమైన దాహం.",
                    "రెండు రోజులకు మించి విరేచనాలు తగ్గకపోతే వెంటనే డాక్టర్ వద్దకు వెళ్లండి.",
                ],
            },
        },
    ),
    "mild_headache": ApprovedRemedy(
        remedy_id="mild_headache",
        title="Tension & Exertional Headache Relief",
        symptom_keywords=[
            "headache", "mild head ache", "head pain", "tension headache",
            "தலைவலி", "லேசான தலைவலி",
            "सिरदर्द", "हल्का सिर दर्द", "सिर में भारीपन",
            "తలనొప్పి", "తల బరువు",
        ],
        care_steps=[
            "Rest in a quiet, dark, well-ventilated room away from bright sunlight and loud noise.",
            "Drink 2 to 3 glasses of clean drinking water to treat potential dehydration-induced headache.",
            "Apply a cool damp cloth across your forehead or a gentle warm compress to the back of the neck.",
            "Perform gentle neck and shoulder rotations to relieve tension from muscular tightness.",
            "Avoid staring at mobile screens, television, or direct glare for at least 2 hours.",
        ],
        monitoring_signs=[
            "Headache increasing in severity despite resting in a dark room and drinking water.",
            "Onset of mild nausea or light sensitivity.",
        ],
        seek_doctor_if=[
            "Sudden, explosive severe headache reaching peak intensity within seconds ('thunderclap headache').",
            "Headache accompanied by stiff neck, high fever, or vomiting.",
            "Associated neurological signs: blurred vision, slurred speech, confusion, or weakness in arms/legs.",
            "Headache developing following any recent fall, bump, or head injury.",
            "Pain persisting continuously for more than 24 hours.",
        ],
        translations={
            "ta-IN": {
                "care_steps": [
                    "அமைதியான, வெளிச்சம் குறைவான, காற்றோட்டமான அறையில் படுத்து ஓய்வெடுக்கவும்.",
                    "போதுமான அளவு (2-3 டம்ளர்) சுத்தமான குடிநீர் பருகவும்.",
                    "நெற்றியில் குளிர்ந்த துணியை வைத்து ஒத்தடம் கொடுக்கவும்.",
                    "செல்போன் மற்றும் டிவி பார்ப்பதை தவிர்க்கவும்.",
                ],
                "seek_doctor_if": [
                    "திடீரென வெடிக்கும் போன்ற மிகக் கடுமையான தலைவலி ஏற்பட்டால்.",
                    "கழுத்து விறைப்பு, காய்ச்சல் அல்லது வாந்தியுடன் தலைவலி இருந்தால்.",
                    "பார்வை மங்குதல், பேசுவதில் குழப்பம் அல்லது கை, கால்களில் பலவீனம் ஏற்பட்டால்.",
                    "தலையில் அடிபட்ட பிறகு ஏற்படும் தலைவலிக்கு உடனடியாக மருத்துவரை அணுகவும்.",
                ],
            },
            "hi-IN": {
                "care_steps": [
                    "शांत, हवादार और मंद रोशनी वाले कमरे में आंखें बंद करके आराम करें।",
                    "2 से 3 गिलास साफ पानी पिएं ताकि शरीर में पानी की कमी न रहे।",
                    "माथे पर ठंडे पानी की पट्टी या गर्दन के पीछे हल्का सेक करें।",
                    "मोबाइल या टीवी स्क्रीन से दूरी बनाएं।",
                ],
                "seek_doctor_if": [
                    "अचानक बहुत तेज या असहनीय सिरदर्द शुरू होना।",
                    "सिरदर्द के साथ गर्दन में अकड़न, तेज बुखार या उल्टी होना।",
                    "धुंधला दिखाई देना, बोलने में लड़खड़ाहट या शरीर के किसी हिस्से में कमजोरी आना।",
                    "सिर पर चोट लगने के बाद सिरदर्द होना।",
                ],
            },
            "te-IN": {
                "care_steps": [
                    "నిశ్శబ్దమైన, చల్లని మరియు చీకటి గదిలో విశ్రాంతి తీసుకోండి.",
                    "తగినంత మంచినీరు (2-3 గ్లాసులు) తాగండి.",
                    "నుదుటిపై చల్లని గుడ్డతో కాపడం పెట్టండి.",
                    "మొబైల్ ఫోన్లు మరియు టీవీ స్క్రీన్లకు దూరంగా ఉండండి.",
                ],
                "seek_doctor_if": [
                    "అకస్మాత్తుగా తీవ్రమైన తలనొప్పి రావడం.",
                    "తలనొప్పితో పాటు మెడ బిగుతుగా ఉండటం, జ్వరం లేదా వాంతులు రావడం.",
                    "కంటి చూపు మసకబారడం లేదా మాట్లాడటంలో ఇబ్బంది కలగడం.",
                    "తలకి దెబ్బ తగిలిన తర్వాత తలనొప్పి రావడం.",
                ],
            },
        },
    ),
    "body_ache_fatigue": ApprovedRemedy(
        remedy_id="body_ache_fatigue",
        title="Muscular Aches & Exertional Fatigue Care",
        symptom_keywords=[
            "body pain", "body ache", "muscle ache", "fatigue", "tiredness", "weakness",
            "உடல் வலி", "அசதி", "மூட்டு வலி",
            "बदन दर्द", "थकान", "मांसपेशियों में दर्द", "कमजोरी",
            "ఒళ్లు నొప్పులు", "నీరసం", "అలసట",
        ],
        care_steps=[
            "Ensure full physical rest; refrain from field labor, heavy lifting, or strenuous activity for 24-48 hours.",
            "Drink plenty of water and warm fluids like lemon water with a pinch of salt or clear vegetable broth.",
            "Take a warm bath or apply a warm water compress to tight muscle groups for 15 minutes.",
            "Do gentle, slow limb stretching to prevent muscle stiffness.",
            "Ensure at least 8 hours of uninterrupted night sleep on a firm sleeping surface.",
        ],
        monitoring_signs=[
            "Muscle soreness worsening or turning into localized burning pain.",
            "Onset of swelling or redness over a specific joint.",
        ],
        seek_doctor_if=[
            "Severe pain preventing normal walking, standing, or bearing weight.",
            "Pain accompanied by high continuous fever, shaking chills, or dark reddish urine.",
            "Any chest discomfort, tightness, or pain spreading to the left shoulder or back.",
            "Swelling, localized heat, and throbbing pain in the calves or legs.",
            "Aches persisting for more than 3 days without relief.",
        ],
        translations={
            "ta-IN": {
                "care_steps": [
                    "கடினமான வேலைகளை தவிர்த்து 24-48 மணி நேரம் முழு ஓய்வு எடுக்கவும்.",
                    "வெதுவெதுப்பான நீரில் குளிப்பது அல்லது ஒத்தடம் கொடுப்பது தசை வலியை குறைக்கும்.",
                    "போதுமான அளவு நீர் மற்றும் எலுமிச்சை சாறு அருந்தவும்.",
                    "இரவில் குறைந்தது 8 மணி நேரம் நல்ல தூக்கம் அவசியம்.",
                ],
                "seek_doctor_if": [
                    "நடக்க முடியாத அளவுக்கு கடுமையான வலி இருந்தால்.",
                    "மார்பு வலி, நெஞ்சு படபடப்பு அல்லது மூச்சு திணறல் ஏற்பட்டால்.",
                    "மூட்டுகளில் வீக்கம், சிவந்து போதல் மற்றும் கடுமையான சூடு இருந்தால்.",
                    "3 நாட்களுக்கு மேலாக வலி தொடர்ந்தால் மருத்துவரை பார்க்கவும்.",
                ],
            },
            "hi-IN": {
                "care_steps": [
                    "भारी काम या मेहनत से बचें और 1-2 दिन पर्याप्त आराम करें।",
                    "गुनगुने पानी से नहाएं या दर्द वाली जगह पर गर्म कपड़े से सिकाई करें।",
                    "खूब पानी, सूप या नींबू पानी पिएं।",
                    "रात में 8 घंटे की पूरी और गहरी नींद लें।",
                ],
                "seek_doctor_if": [
                    "खड़े होने या चलने में असमర్థता हो।",
                    "सीने में दर्द या भारीपन जो हाथ या पीठ तक फैले।",
                    "जोड़ों में सूजन, लालिमा और असहनीय दर्द हो।",
                    "तेज बुखार या पेशाब का रंग गहरा लाल/भूरा होना।",
                ],
            },
            "te-IN": {
                "care_steps": [
                    "శారీరక శ్రమకు దూరంగా ఉండి పూర్తి విశ్రాంతి తీసుకోండి.",
                    "గోరువెచ్చని నీటితో స్నానం చేయడం వల్ల కండరాల నొప్పులు తగ్గుతాయి.",
                    "మంచినీరు, పండ్ల రసాలు ఎక్కువగా తీసుకోండి.",
                    "రాత్రి వేళ 8 గంటల పాటు నిద్రపోవాలి.",
                ],
                "seek_doctor_if": [
                    "నడవలేనంత తీవ్రమైన నొప్పులు రావడం.",
                    "ఛాతీలో నొప్పి లేదా అసౌకర్యం కలగడం.",
                    "కీళ్ల వాపు, ఎర్రబడటం మరియు తీవ్రమైన మంట ఉండటం.",
                    "3 రోజులకు మించి నొప్పులు తగ్గకపోవడం.",
                ],
            },
        },
    ),
    "mild_indigestion": ApprovedRemedy(
        remedy_id="mild_indigestion",
        title="Mild Indigestion & Acidity Management",
        symptom_keywords=[
            "acidity", "indigestion", "gas", "bloating", "mild stomach ache", "heartburn", "sour burps",
            "நெஞ்செரிச்சல்", "வாயு", "செரிமானமின்மை", "அசிடிட்டி",
            "एसिडिटी", "गैस", "अपच", "खट्टी डकार", "पेट फूलना",
            "కడుపులో మంట", "అజీర్ణం", "గ్యాస్",
        ],
        care_steps=[
            "Eat smaller, more frequent light meals rather than 2 large heavy meals.",
            "Avoid deep-fried, excessively oily, heavily spiced, and sour foods for the next 48 hours.",
            "Drink clean room-temperature water sip-by-sip between meals, not large gulps during meals.",
            "Do not lie down flat immediately after eating; wait at least 2 hours before lying down.",
            "Elevate the head end of your sleeping cot by 4-6 inches if experiencing night heartburn.",
        ],
        monitoring_signs=[
            "Frequent sour regurgitation or sensation of fullness after only a few bites.",
            "Mild epigastric discomfort after spicy meals.",
        ],
        seek_doctor_if=[
            "Chest pain, crushing pressure, or heaviness that radiates to the neck, jaw, or left arm (rule out heart attack).",
            "Difficulty or intense pain when swallowing solid foods or liquids.",
            "Vomiting black coffee-ground material or passing black tarry stools.",
            "Unexplained weight loss or persistent vomiting.",
            "Severe continuous stomach pain that wakes you up from sleep.",
        ],
        translations={
            "ta-IN": {
                "care_steps": [
                    "ஒரே நேரத்தில் அதிகமாக சாப்பிடாமல், சிறுக சிறுக பல வேளைகளாக சாப்பிடவும்.",
                    "எண்ணெய், அதிக காரம், புளிப்பு நிறைந்த உணவுகளை தவிர்க்கவும்.",
                    "சாப்பிட்ட உடனே படுக்க வேண்டாம்; சாப்பிட்ட பிறகு குறைந்தது 2 மணி நேரம் கழித்து படுக்கவும்.",
                    "சாப்பாட்டிற்கு நடுவே அதிக தண்ணீர் குடிப்பதை தவிர்க்கவும்.",
                ],
                "seek_doctor_if": [
                    "நெஞ்சு வலி அல்லது அழுத்தம் தாடை, தோள்பட்டை வரை பரவினால்.",
                    "உணவை விழுங்குவதில் சிரமம் அல்லது வலி இருந்தால்.",
                    "வாந்தியில் ரத்தம் அல்லது கருப்பு நிற மலம் போனால் உடனே மருத்துவரிடம் செல்லவும்.",
                ],
            },
            "hi-IN": {
                "care_steps": [
                    "एक बार में ज्यादा खाने के बजाय थोड़ा-थोड़ा करके दिन में कई बार खाएं।",
                    "ज्यादा तला-भुना, मिर्च-मसालेदार और खट्टा खाना बिल्कुल न खाएं।",
                    "खाना खाने के तुरंत बाद न लेटें, कम से कम 2 घंटे बाद ही सोएं।",
                    "भोजन के दौरान घूंट-घूंट करके पानी पिएं, एक साथ बहुत पानी न पिएं।",
                ],
                "seek_doctor_if": [
                    "सीने में तेज दर्द या भारीपन जो बांह या जबड़े तक फैले।",
                    "खाना या पानी निगलने में कठिनाई या दर्द होना।",
                    "उल्टी में खून आना या काला मल आना।",
                    "पेट में लगातार असहनीय दर्द होना।",
                ],
            },
            "te-IN": {
                "care_steps": [
                    "ఒకేసారి ఎక్కువగా తినకుండా, తక్కువ మోతాదులో ఎక్కువసార్లు తినండి.",
                    "నూనె, ఎక్కువ కారం మరియు మసాలాలు ఉన్న ఆహారానికి దూరంగా ఉండండి.",
                    "తిన్న వెంటనే పడుకోకండి, కనీసం రెండు గంటల తర్వాతే పడుకోవాలి.",
                ],
                "seek_doctor_if": [
                    "ఛాతీలో నొప్పి లేదా ఒత్తిడి చేతికి లేదా దవడకు పాకడం.",
                    "ఆహారం మింగడంలో తీవ్రమైన నొప్పి లేదా ఇబ్బంది కలగడం.",
                    "వాంతిలో రక్తం పడటం లేదా మలం నల్లగా రావడం.",
                ],
            },
        },
    ),
    "mild_leg_pain": ApprovedRemedy(
        remedy_id="mild_leg_pain",
        title="Mild Leg & Calf Muscle Strain Care",
        symptom_keywords=[
            "leg pain", "calf pain", "thigh pain", "muscle cramp", "tired legs", "aching legs",
            "கால் வலி", "கால் தசைப்பிடிப்பு", "தசை வலி",
            "टांगों में दर्द", "पैर दर्द", "पिंडलियों में दर्द", "मांसपेशियों में खिंचाव",
            "కాలి నొప్పి", "కాళ్ల నొప్పులు", "పిక్కల నొప్పి",
        ],
        care_steps=[
            "Rest the affected leg and avoid prolonged standing, brisk walking, or heavy lifting for 24 to 48 hours.",
            "Keep the leg gently elevated on a cushion or folded pillow while sitting or sleeping to reduce muscle congestion.",
            "Apply a cold compress (ice wrapped in a clean cloth) for 15 minutes twice daily to relieve acute muscle strain.",
            "Drink plenty of clean water and oral fluids to avoid dehydration-related muscle cramps.",
            "Perform very gentle calf and ankle stretching once acute soreness begins to ease.",
        ],
        monitoring_signs=[
            "Increasing swelling, noticeable warmth, or redness developing in one calf or leg.",
            "Pain persisting despite 48 hours of rest and elevation.",
        ],
        seek_doctor_if=[
            "Sudden swelling, intense heat, or redness in one calf (warning sign of deep vein thrombosis).",
            "Inability to bear weight or take even a few steps on the leg.",
            "Severe pain following a direct fall, twist, or trauma to the knee or leg.",
            "Leg pain accompanied by chest pain, shortness of breath, or coughing up blood (call 108 emergency immediately).",
            "Cold, pale, or bluish foot or loss of sensation in the leg.",
        ],
        translations={
            "ta-IN": {
                "care_steps": [
                    "24 முதல் 48 மணி நேரம் நீண்ட நேரம் நிற்பது அல்லது நடப்பதை தவிர்த்து காலுக்கு ஓய்வு அளிக்கவும்.",
                    "படுக்கும்போது அல்லது அமரும்போது காலை தலையணையின் மீது லேசாக உயர்த்தி வைக்கவும்.",
                    "தசை வலி உள்ள பகுதியில் சுத்தமான துணியில் சுற்றிய ஐஸ் கட்டியால் 15 நிமிடங்கள் ஒத்தடம் கொடுக்கவும்.",
                    "தசைப்பிடிப்பு வராமல் இருக்க போதுமான அளவு சுத்தமான குடிநீர் பருகவும்.",
                ],
                "seek_doctor_if": [
                    "ஒரு காலில் மட்டும் திடீர் வீக்கம், அதீத சூடு அல்லது சிவந்து போதல் இருந்தால்.",
                    "காலில் நின்றோ நடந்தோ எடை தாங்க முடியாமல் போனால்.",
                    "கால் வலியுடன் நெஞ்சு வலி, மூச்சுத்திணறல் அல்லது இருமலில் ரத்தம் வந்தால் உடனே 108 அழைக்கவும்.",
                    "கால் மரத்துப்போவது அல்லது பாதத்தில் குளிர்ச்சி ஏற்பட்டால் உடனே மருத்துவரை அணுகவும்.",
                ],
            },
            "hi-IN": {
                "care_steps": [
                    "24 से 48 घंटे तक पैरों को आराम दें और ज्यादा देर तक खड़े रहने या भारी काम करने से बचें।",
                    "बैठते या सोते समय पैर के नीचे तकिया रखकर उसे हल्का ऊंचा रखें।",
                    "दर्द वाली जगह पर कपड़े में लपेटकर बर्फ से 15 मिनट हल्की सिकाई करें।",
                    "मांसपेशियों में ऐंठन से बचने के लिए भरपूर पानी और तरल पदार्थ पिएं।",
                ],
                "seek_doctor_if": [
                    "किसी एक पैर या पिंडली में अचानक सूजन, अत्यधिक गर्माहट या लालिमा आना।",
                    "पैर पर बिल्कुल वजन न दे पाना या चलने में असमर्थ होना।",
                    "पैर दर्द के साथ सीने में दर्द, सांस लेने में तकलीफ या खांसी में खून आना (तुरंत 108 पर कॉल करें)।",
                    "पैर या पंजे का ठंडा पड़ना या सुन्न हो जाना।",
                ],
            },
            "te-IN": {
                "care_steps": [
                    "ఎక్కువ సేపు నిలబడకుండా 24-48 గంటలు కాళ్లకు తగినంత విశ్రాంతి ఇవ్వండి.",
                    "పడుకునేటప్పుడు లేదా కూర్చునేటప్పుడు కాళ్ల కింద దిండు పెట్టుకుని కొద్దిగా ఎత్తుగా ఉంచండి.",
                    "నొప్పి ఉన్న ప్రదేశంలో శుభ్రమైన గుడ్డలో మంచుగడ్డ చుట్టి 15 నిమిషాలు కాపడం పెట్టండి.",
                    "కండరాల నొప్పులు రాకుండా ఉండటానికి తగినంత మంచినీరు తాగండి.",
                ],
                "seek_doctor_if": [
                    "ఒక కాలి పిక్కలో అకస్మాత్తుగా వాపు, తీవ్రమైన వేడి లేదా ఎరుపు రావడం.",
                    "కాలుపై అస్సలు నిలబడలేకపోవడం లేదా నడవలేకపోవడం.",
                    "కాలి నొప్పితో పాటు ఛాతీ నొప్పి లేదా శ్వాస తీసుకోవడంలో ఇబ్బంది ఉండటం (వెంటనే 108 కు కాల్ చేయండి).",
                    "కాలు లేదా పాదం చల్లబడిపోవడం లేదా తిమ్మిరి రావడం.",
                ],
            },
        },
    ),
    "mild_hair_loss": ApprovedRemedy(
        remedy_id="mild_hair_loss",
        title="General Scalp & Mild Hair Fall Self-Care",
        symptom_keywords=[
            "hair loss", "hair fall", "thinning hair", "dandruff", "scalp itch", "falling hair",
            "முடி உதிர்தல்", "முடி கொட்டுதல்", "பொடுகு", "தலையில் அரிப்பு",
            "बाल झड़ना", "बाल गिरना", "रूसी", "सिर में खुजली", "बालों का पतला होना",
            "జుట్టు రాలడం", "తల దురద", "చుండ్రు",
        ],
        care_steps=[
            "Wash hair gently using clean room-temperature or lukewarm water; avoid very hot water.",
            "Avoid tight hairstyles, vigorous towel rubbing, and harsh chemical treatments or heat dryers.",
            "Eat a balanced diet rich in natural protein, iron, and green leafy vegetables (spinach, lentils, eggs, nuts).",
            "Gently massage the scalp with clean pure coconut or sesame oil for 5 to 10 minutes once or twice weekly.",
            "Ensure 7 to 8 hours of adequate sleep and manage everyday stress levels.",
        ],
        monitoring_signs=[
            "Noticeable clumps of hair falling out daily exceeding normal shedding.",
            "Mild itching, scaling, or burning sensation across the scalp.",
        ],
        seek_doctor_if=[
            "Sudden, patchy hair loss causing distinct smooth round bald spots (alopecia areata).",
            "Severe scalp redness, persistent pain, oozing, crusting, or pus discharge.",
            "Hair fall accompanied by unexplained weight changes, chronic fatigue, cold intolerance, or irregular menstrual cycles.",
            "Rapid, widespread hair shedding starting after beginning new systemic medications.",
        ],
        translations={
            "ta-IN": {
                "care_steps": [
                    "தலைமுடியை அதிக சூடான நீரில் கழுவாமல், வெதுவெதுப்பான அல்லது குளிர்ந்த நீரில் மென்மையாக அலசவும்.",
                    "தலைமுடியை இறுக்கமாக கட்டுவதையோ, துண்டால் வேகமாக தேய்ப்பதையோ தவிர்க்கவும்.",
                    "கீரை, பருப்பு வகைகள், முட்டை போன்ற புரதம் மற்றும் இரும்புச்சத்து நிறைந்த உணவுகளை அதிகம் உண்ணவும்.",
                    "வாரத்திற்கு இருமுறை சுத்தமான தேங்காய் எண்ணெயால் தலையில் மென்மையாக மசாஜ் செய்யவும்.",
                ],
                "seek_doctor_if": [
                    "திடீரென வட்ட வடிவில் வழுக்கை போன்ற திட்டுகள் தோன்றினால்.",
                    "தலையில் அதிக சிவத்தல், கொப்பளங்கள், சீழ் அல்லது தாங்க முடியாத அரிப்பு இருந்தால்.",
                    "முடி கொட்டுதலுடன் உடல் எடை குறைவு, தீவிர சோர்வு அல்லது மாதவிடாய் பிரச்சனைகள் இருந்தால் மருத்துவரை அணுகவும்.",
                ],
            },
            "hi-IN": {
                "care_steps": [
                    "बालों को बहुत गर्म पानी से न धोएं, ताजे या हल्के गुनगुने पानी से धीरे-धीरे धोएं।",
                    "बालों को जोर से तौलिए से न रगड़ें और कसकर बांधने से बचें।",
                    "हरी पत्तेदार सब्जियां, दालें और पोषण युक्त संतुलित आहार लें।",
                    "सप्ताह में 1-2 बार शुद्ध नारियल तेल से सिर की हल्की मालिश करें।",
                ],
                "seek_doctor_if": [
                    "अचानक सिर में गोल सिक्के जैसे गंजेपन के चकत्ते (पैच) दिखना।",
                    "सिर की त्वचा पर अत्यधिक लाली, पपड़ी, दाने या मवाद आना।",
                    "बाल झड़ने के साथ अचानक वजन बदलना, अत्यधिक थकान या कमजोरी महसूस होना।",
                ],
            },
            "te-IN": {
                "care_steps": [
                    "తలస్నానానికి వేడి నీళ్లకు బదులుగా గోరువెచ్చని లేదా చల్లని నీటిని ఉపయోగించండి.",
                    "జుట్టును టవల్‌తో గట్టిగా రుద్దకండి మరియు బిగుతుగా ముడి వేయకండి.",
                    "ఆకుకూరలు, పప్పుధాన్యాలు వంటి పోషక విలువలున్న ఆహారం తీసుకోండి.",
                    "వారానికి ఒకసారి లేదా రెండుసార్లు కొబ్బరి నూనెతో తలకు సున్నితంగా మర్దన చేయండి.",
                ],
                "seek_doctor_if": [
                    "తలమీద అకస్మాత్తుగా గుండ్రని మచ్చలుగా జుట్టు రాలిపోవడం.",
                    "తల చర్మంపై తీవ్రమైన ఎరుపు, కురుపులు లేదా చీము పట్టడం.",
                    "జుట్టు రాలడంతో పాటు విపరీతమైన అలసట లేదా బరువు తగ్గడం గమనిస్తే వెంటనే వైద్యుడిని సంప్రదించండి.",
                ],
            },
        },
    ),
}


def find_approved_remedy(symptom_names: List[str], chief_complaint: str = "") -> Optional[ApprovedRemedy]:
    """
    Match reported clinical symptoms against the approved library.
    Returns the most relevant ApprovedRemedy, or None if no approved match exists.
    """
    search_text = (chief_complaint + " " + " ".join(symptom_names)).lower()
    
    # Priority matching order
    for remedy_id, remedy in APPROVED_REMEDY_LIBRARY.items():
        for kw in remedy.symptom_keywords:
            if kw.lower() in search_text:
                return remedy
    return None


def get_default_home_remedy_guidance(patient_language: Optional[str] = "en-IN") -> HomeRemedyGuidance:
    """
    Fixed approved clinical fallback when no specific home remedy matches (B6.2).
    Never hallucinates unverified advice; guides patient to consult a doctor.
    """
    lang_code = patient_language or "en-IN"
    lang_key = lang_code if lang_code in ("ta-IN", "hi-IN", "te-IN") else (
        "ta-IN" if "ta" in lang_code.lower() else (
            "hi-IN" if "hi" in lang_code.lower() else (
                "te-IN" if "te" in lang_code.lower() else "en-IN"
            )
        )
    )

    base_care_steps = [
        "Please consult a healthcare professional at your local Primary Health Centre (PHC) for a clinical evaluation of your symptoms.",
        "Take adequate physical rest in a well-ventilated, quiet room and avoid strenuous labor or heavy lifting.",
        "Stay well hydrated by drinking clean boiled and cooled water, light buttermilk, or oral fluids.",
        "Do not consume unprescribed medications, antibiotics, or unverified remedies without a clinician's advice.",
    ]

    base_monitoring = [
        "Symptoms increasing in severity or not easing after 24 to 48 hours of rest.",
        "Onset of persistent nausea or difficulty keeping food or fluids down.",
        "New symptoms such as dizziness, high fever, or unexpected swelling.",
    ]

    base_seek_doctor = [
        "Any difficulty breathing, shortness of breath, or chest heaviness.",
        "High continuous fever above 101°F that does not respond to rest.",
        "Any active bleeding (coughing up blood, blood in vomit, stool, or vaginal bleeding).",
        "Severe continuous pain or inability to drink liquids and stay hydrated.",
        "Sudden worsening of symptoms — immediately call 108 or 112 emergency services.",
    ]

    translations = {
        "ta-IN": {
            "care_steps": [
                "உங்கள் அறிகுறிகளுக்கு தகுந்த பரிசோதனை பெற அருகிலுள்ள அரசு ஆரம்ப சுகாதார நிலைய (PHC) மருத்துவரை அணுகவும்.",
                "கடினமான வேலைகளை தவிர்த்து காற்றோட்டமான அறையில் போதுமான ஓய்வு எடுக்கவும்.",
                "காய்ச்சி ஆறிய சுத்தமான தண்ணீர் மற்றும் மோர் போன்ற நீர் ஆகாரங்களை அதிகம் பருகவும்.",
                "மருத்துவர் பரிந்துரைக்காத மாத்திரைகளையோ அல்லது ஆண்டிபயாடிக்குகளையோ சுயமாக உட்கொள்ள வேண்டாம்.",
            ],
            "seek_doctor_if": [
                "மூச்சுத்திணறல், மூச்சு விடுவதில் சிரமம் அல்லது நெஞ்சு பாரம் ஏற்பட்டால்.",
                "101°F க்கு மேல் தொடர் காய்ச்சல் இருந்தால்.",
                "எந்தவொரு ரத்தப்போக்கும் (இருமலில், வாந்தியில், மலத்தில்) ஏற்பட்டால் உடனே மருத்துவமனைக்கு செல்லவும்.",
                "அறிகுறிகள் திடீரென தீவிரமடைந்தால் உடனடியாக 108 அவசர ஆம்புலன்ஸை அழைக்கவும்.",
            ],
        },
        "hi-IN": {
            "care_steps": [
                "अपने लक्षणों की जांच के लिए नजदीकी प्राथमिक स्वास्थ्य केंद्र (PHC) के चिकित्सक से परामर्श करें।",
                "हवादार कमरे में पर्याप्त आराम करें और भारी शारीरिक श्रम से बचें।",
                "उबला और ठंडा किया गया साफ पानी व तरल पदार्थ भरपूर मात्रा में पिएं।",
                "डॉक्टर की सलाह के बिना कोई भी दवा या एंटीबायोटिक खुद से न लें।",
            ],
            "seek_doctor_if": [
                "सांस लेने में कोई भी तकलीफ या सीने में भारीपन होना।",
                "101°F से अधिक तेज बुखार जो आराम करने पर भी न उतरे।",
                "किसी भी प्रकार का रक्तस्राव (उल्टी, मल, खांसी में खून आना)।",
                "लक्षणों के अचानक बिगड़ने पर तुरंत 108 या 112 आपातकालीन सेवा पर कॉल करें।",
            ],
        },
        "te-IN": {
            "care_steps": [
                "మీ లక్షణాల సరైన పరీక్ష కోసం స్థానిక ప్రాథమిక ఆరోగ్య కేంద్రం (PHC) వైద్యుడిని సంప్రదించండి.",
                "గాలి వెలుతురు ఉన్న గదిలో తగినంత విశ్రాంతి తీసుకోండి మరియు కష్టమైన పనులు చేయకండి.",
                "కాచి చల్లార్చిన మంచినీరు, మజ్జిగ వంటి ద్రవాలను ఎక్కువగా తాగండి.",
                "వైద్యుడి సలహా లేకుండా ఎలాంటి మందులు లేదా యాంటీబయాటిక్స్ సొంతంగా తీసుకోకండి.",
            ],
            "seek_doctor_if": [
                "శ్వాస తీసుకోవడంలో ఇబ్బంది లేదా ఛాతీలో బరువుగా ఉండటం.",
                "101°F కంటే ఎక్కువ తీవ్ర జ్వరం తగ్గకపోవడం.",
                "వాంతుల్లో, మలంలో లేదా దగ్గులో రక్తం పడటం.",
                "పరిస్థితి విషమిస్తే వెంటనే 108 లేదా 112 అత్యవసర సేవలకు కాల్ చేయండి.",
            ],
        },
    }

    trans_steps = translations.get(lang_key, {}).get("care_steps")
    trans_seek = translations.get(lang_key, {}).get("seek_doctor_if")

    care_objects = []
    for i, step in enumerate(base_care_steps):
        t_step = trans_steps[i] if (trans_steps and i < len(trans_steps)) else None
        care_objects.append(HomeRemedyCareStep(step=step, translated_step=t_step))

    return HomeRemedyGuidance(
        care_steps=care_objects,
        monitoring_signs=base_monitoring,
        seek_doctor_if=base_seek_doctor,
        translated_care_steps=trans_steps,
        translated_seek_doctor_if=trans_seek,
        language=patient_language,
        disclaimer=(
            "Approved self-care information (demonstration). "
            "This information is for mild, self-limiting symptoms only and does not replace medical consultation. "
            "If any warning signs appear, please seek medical care or call 108 immediately."
        ),
    )


def get_approved_home_remedy_guidance(
    summary: Any,
    patient_language: Optional[str] = "en-IN",
) -> Optional[HomeRemedyGuidance]:
    """
    Construct validated HomeRemedyGuidance strictly from the approved self-care library.
    Includes translated care steps and 'seek doctor if' triggers for the patient.
    """
    non_negated_symptoms = [s.name for s in getattr(summary, "symptoms", []) if not getattr(s, "negated", False)]
    chief_complaint = getattr(summary, "chief_complaint", "")
    
    remedy = find_approved_remedy(non_negated_symptoms, chief_complaint)
    if not remedy:
        return None

    lang_code = patient_language or "en-IN"
    lang_key = lang_code if lang_code in remedy.translations else (
        "ta-IN" if "ta" in lang_code.lower() else (
            "hi-IN" if "hi" in lang_code.lower() else (
                "te-IN" if "te" in lang_code.lower() else None
            )
        )
    )

    translated_steps = None
    translated_seek_doctor = None
    if lang_key and lang_key in remedy.translations:
        trans_data = remedy.translations[lang_key]
        translated_steps = trans_data.get("care_steps")
        translated_seek_doctor = trans_data.get("seek_doctor_if")

    care_step_objects = []
    for i, step in enumerate(remedy.care_steps):
        trans_step = translated_steps[i] if (translated_steps and i < len(translated_steps)) else None
        care_step_objects.append(HomeRemedyCareStep(step=step, translated_step=trans_step))

    return HomeRemedyGuidance(
        care_steps=care_step_objects,
        monitoring_signs=remedy.monitoring_signs,
        seek_doctor_if=remedy.seek_doctor_if,
        translated_care_steps=translated_steps,
        translated_seek_doctor_if=translated_seek_doctor,
        language=patient_language,
        disclaimer=(
            "Approved self-care information (demonstration). "
            "This information is for mild, self-limiting symptoms only and does not replace medical consultation. "
            "If any warning signs appear, please seek medical care or call 108 immediately."
        ),
    )

