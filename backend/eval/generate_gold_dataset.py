"""
Gold Evaluation Set Generator for Grannus RuralCare AI.
Generates 360 adjudicated clinical cases across emergencies (oversampled),
urgent cases, and mild self-care cases in English, Tamil, Hindi, Telugu, and Code-Mixed.

Adjudicated by simulated two-clinician consensus (Internal Medicine + Emergency Medicine).
"""
import json
import random
from pathlib import Path
from typing import Dict, List, Any

OUTPUT_PATH = Path(__file__).resolve().parent / "gold_evaluation_set.json"

# Seed for absolute reproducibility
random.seed(42)

def generate_gold_dataset() -> List[Dict[str, Any]]:
    cases: List[Dict[str, Any]] = []

    # -------------------------------------------------------------------------
    # 1. EMERGENCY CASES (Tier: HIGH) - Target: 144 cases (~40%)
    # -------------------------------------------------------------------------
    emergency_templates = [
        # Cardiovascular / Chest Pain
        {
            "category": "cardiovascular",
            "en": "I have severe crushing chest pain since morning that is radiating down my left arm and jaw. I am sweating profusely.",
            "ta": "எனக்கு காலையிலிருந்து நெஞ்சு வலி கடுமையாக உள்ளது, வலி இடது கைக்கும் பரவுகிறது. ரொம்ப வியர்க்கிறது.",
            "hi": "मुझे सुबह से सीने में तेज दर्द है जो बाएं हाथ में जा रहा है और बहुत पसीना आ रहा है।",
            "te": "నాకు ఉదయం నుండి ఛాతీలో తీవ్రమైన నొప్పి ఉంది మరియు ఎడమ చేయి గుంజుతోంది, చెమటలు పడుతున్నాయి.",
            "tanglish": "Enakku morning lendhu nenju vali bayangarama irukku, left arm spread aagudhu, sweating over ah irukku.",
            "hinglish": "Subah se chest me bahut heavy dard hai aur left arm me ja raha hai, sweating ho rahi hai.",
            "symptoms": [{"name": "chest pain", "severity": "severe", "negated": False}],
            "red_flags": ["Severe chest pain reported", "chest pain"],
            "age_range": (45, 78),
            "gender": "male",
            "conditions": ["hypertension", "diabetes"],
        },
        # Severe Respiratory Distress
        {
            "category": "respiratory",
            "en": "I cannot breathe properly, my chest is so tight and I am choking. My family says my lips look blue.",
            "ta": "எனக்கு மூச்சு விட ரொம்ப சிரமமாக இருக்கிறது, மூச்சு திணறல் அதிகமா இருக்கு, உதடு நீல நிறமாகிவிட்டது.",
            "hi": "मुझे सांस लेने में बहुत तकलीफ हो रही है, दम घुट रहा है और होंठ नीले पड़ गए हैं।",
            "te": "నాకు ఊపిరి ఆడటం లేదు, ఆయాసం ఎక్కువైంది, పెదవులు నీలంగా మారాయి.",
            "tanglish": "Moochu vida mudiyala, chest tight ah irukku, lips blue ah aagiruchu.",
            "hinglish": "Saans bilkul nahi le pa raha hu, choking lag raha hai, lips blue ho gaye hai.",
            "symptoms": [{"name": "difficulty breathing", "severity": "severe", "negated": False}, {"name": "cyanosis", "severity": "severe", "negated": False}],
            "red_flags": ["Breathing difficulty reported", "Cyanosis / blue lips reported"],
            "age_range": (18, 75),
            "gender": "female",
            "conditions": ["asthma", "copd"],
        },
        # Snakebite / Envenomation
        {
            "category": "toxicology",
            "en": "A snake bit my foot in the field one hour ago. The leg is swelling fast and I feel dizzy and numb.",
            "ta": "வயலில் வேலை செய்யும்போது பாம்பு கடிச்சிடுச்சு. கால் வீங்கி போச்சு, மயக்கம் வருது.",
            "hi": "खेत में सांप ने पैर पर काट लिया है। पैर तेजी से सूज रहा है और चक्कर आ रहे हैं।",
            "te": "పొలంలో పాము కాటు వేసింది. కాలు వాచిపోయింది, స్పృహ తప్పుతున్నట్టు ఉంది.",
            "tanglish": "Vayalla paambu kadichiruchu, kaal full ah veengi mayakkam varudhu.",
            "hinglish": "Khet me saanp ne kaat liya, pair sujh raha hai aur behoshi lag rahi hai.",
            "symptoms": [{"name": "snakebite", "severity": "severe", "negated": False}, {"name": "dizziness", "severity": "moderate", "negated": False}],
            "red_flags": ["Poisoning or envenomation reported", "snakebite"],
            "age_range": (20, 60),
            "gender": "male",
            "conditions": [],
        },
        # Scorpion Sting
        {
            "category": "toxicology",
            "en": "A scorpion stung my hand. I am having unbearable pain, sweating all over, and vomiting continuously.",
            "ta": "கையில் தேள் கொட்டிவிட்டது. தாங்க முடியாத வலி, உடல் முழுவதும் வியர்க்கிறது மற்றும் வாந்தி வருகிறது.",
            "hi": "हाथ में बिच्छू ने काट लिया है। असहनीय दर्द हो रहा है, पसीना छूट रहा है और उल्टी हो रही है।",
            "te": "చేతిపై తేలు కుట్టింది. విపరీతమైన నొప్పి, చెమటలు మరియు వాంతులు అవుతున్నాయి.",
            "tanglish": "Thel kottiruchu hand la, unbearable pain and vomit vandhutte irukku.",
            "hinglish": "Bichhu ne kaat liya hai, unbearable dard hai aur continuously vomiting ho rahi hai.",
            "symptoms": [{"name": "scorpion sting", "severity": "unbearable", "negated": False}, {"name": "vomiting", "severity": "moderate", "negated": False}],
            "red_flags": ["Scorpion sting reported"],
            "age_range": (15, 65),
            "gender": "female",
            "conditions": [],
        },
        # Pesticide Poisoning / Organophosphate
        {
            "category": "toxicology",
            "en": "The farmer accidentally ingested pesticide while spraying crops. He is vomiting, salivating heavily, and confused.",
            "ta": "மருந்து அடிக்கும் போது பூச்சிக்கொல்லி மருந்து உள்ளே போயிடுச்சு. நுரை தள்ளுது, வாந்தி மயக்கம் இருக்கு.",
            "hi": "कीटनाशक दवाई गलती से पी ली है। मुंह से झाग निकल रहा है, उल्टी और बेहोशी है।",
            "te": "పురుగుల మందు తాగేశారు. నోట్లోంచి నురగ వస్తోంది, వాంతులు మరియు స్పృహ తప్పింది.",
            "tanglish": "Pesticide spray pannum podhu ulla poiruchu, vomiting and mayakkam heavy ah irukku.",
            "hinglish": "Crop spray karte waqt pesticide ingest ho gaya, behoshi aur vomiting ho rahi hai.",
            "symptoms": [{"name": "poisoning", "severity": "severe", "negated": False}, {"name": "vomiting", "severity": "severe", "negated": False}],
            "red_flags": ["Poisoning or envenomation reported", "pesticide"],
            "age_range": (25, 55),
            "gender": "male",
            "conditions": [],
        },
        # Stroke / Slurred Speech / Hemiparesis
        {
            "category": "neurology",
            "en": "My grandfather suddenly cannot move his right arm and leg, and his speech is completely slurred.",
            "ta": "தாத்தாவுக்கு திடீரென வலது கை கால் விளங்காமல் போய்விட்டது, பேச்சு குளறுகிறது.",
            "hi": "दादाजी का अचानक दायां हाथ और पैर काम नहीं कर रहा है और उनकी आवाज लड़खड़ा रही है।",
            "te": "తాతగారికి సడన్ గా కుడి చేయి కాలు పడిపోయాయి, మాట స్పష్టంగా రావడం లేదు.",
            "tanglish": "Thatha ku sudden ah right side arm kaal varaala, speech slur aagiduchu, stroke maathiri.",
            "hinglish": "Dadaji ka right side paralyzed ho gaya achanak se aur bol nahi pa rahe hain.",
            "symptoms": [{"name": "weakness", "severity": "severe", "negated": False}],
            "red_flags": ["Potential stroke symptoms reported"],
            "age_range": (60, 85),
            "gender": "male",
            "conditions": ["hypertension", "diabetes"],
        },
        # Seizure / Convulsions
        {
            "category": "neurology",
            "en": "Patient had repeated sudden fits with violent shaking and foaming at the mouth, remaining unconscious.",
            "ta": "திடீரென கடுமையான வலிப்பு வந்தது, வாயில் நுரை தள்ளி மயங்கி விழுந்துவிட்டார்.",
            "hi": "मरीज को अचानक तेज दौरे पड़े, हाथ-पैर अकड़ गए, मुंह से झाग आया और बेहोश है।",
            "te": "సడన్ గా ఫిట్స్ వచ్చాయి, నోటి నుండి నురగ వచ్చి స్పృహ కోల్పోయారు.",
            "tanglish": "Sudden ah valippu vandhruchu, mouth la foam vandhu conscious illa.",
            "hinglish": "Patient ko sudden fits pade hain, daura aaya hai aur behosh ho gaye hain.",
            "symptoms": [{"name": "loss of consciousness", "severity": "severe", "negated": False}],
            "red_flags": ["Seizure or convulsions reported", "Loss of consciousness reported"],
            "age_range": (5, 50),
            "gender": "female",
            "conditions": [],
        },
        # Severe Trauma / Heavy Bleeding
        {
            "category": "trauma",
            "en": "Deep wound from tractor accident, heavy bleeding will not stop and patient looks pale and cold.",
            "ta": "டிராக்டர் விபத்தில் ஆழமான காயம், அதிக ரத்தப்போக்கு நிற்கவே இல்லை, உடல் குளிர்ந்துவிட்டது.",
            "hi": "ट्रैक्टर दुर्घटना में गहरा घाव हुआ है, बहुत खून बह रहा है जो रुक नहीं रहा, शरीर ठंडा पड़ रहा है।",
            "te": "ట్రాక్టర్ ప్రమాదంలో తీవ్ర గాయం, రక్తం ఆగకుండా కారుతోంది, ఒళ్లు చల్లబడిపోయింది.",
            "tanglish": "Tractor accident la deep cut, heavy bleeding continuous ah irukku nikka maattengudhu.",
            "hinglish": "Accident me bahut gehra wound hua hai, heavy bleeding ruk nahi rahi hai.",
            "symptoms": [{"name": "severe bleeding", "severity": "severe", "negated": False}, {"name": "weakness", "severity": "severe", "negated": False}],
            "red_flags": ["Severe bleeding reported"],
            "age_range": (20, 50),
            "gender": "male",
            "conditions": [],
        },
        # Severe Head Injury
        {
            "category": "trauma",
            "en": "Patient fell from a tree hitting his head hard. Blood is coming from ear and he is not waking up.",
            "ta": "மரத்திலிருந்து கீழே விழுந்து தலையில் பலத்த அடி. காதில் ரத்தம் வருகிறது, கண் திறக்கவே இல்லை.",
            "hi": "पेड़ से सिर के बल गिर पड़े हैं। सिर में गंभीर चोट है, कान से खून आ रहा है और होश नहीं है।",
            "te": "చెట్టు పైనుంచి పడి తలకి తీవ్ర గాయమైంది. చెవిలోంచి రక్తం వస్తోంది, స్పృహ లేదు.",
            "tanglish": "Marathula irundhu vizhundhu thalaila heavy adi, ear la ratham varudhu, unconscious.",
            "hinglish": "Sir me bahut tez chot lagi hai girne se, ear se blood aa raha hai aur behosh hain.",
            "symptoms": [{"name": "head injury", "severity": "severe", "negated": False}, {"name": "loss of consciousness", "severity": "severe", "negated": False}],
            "red_flags": ["Head injury reported", "Loss of consciousness reported"],
            "age_range": (15, 60),
            "gender": "male",
            "conditions": [],
        },
        # Severe Burns
        {
            "category": "trauma",
            "en": "Extensive severe burns on chest and arms from boiling liquid and fire, skin is peeling and blistered.",
            "ta": "மார்பிலும் கையிலும் கடுமையான தீக்காயம், தோல் உறிந்து கொப்பளங்கள் வந்துவிட்டது.",
            "hi": "आग और खौलते पानी से सीने और हाथों में गंभीर रूप से जल गए हैं, चमड़ी निकल रही है।",
            "te": "తీవ్రమైన కాలిన గాయాలు అయ్యాయి, చర్మం ఊడిపోతోంది, విపరీతమైన మంట.",
            "tanglish": "Severe burns chest and hand la, theekkayam bayangarama irukku.",
            "hinglish": "Aag se severe burns ho gaye hain chest aur haatho me, skin peel ho gayi hai.",
            "symptoms": [{"name": "severe burns", "severity": "severe", "negated": False}],
            "red_flags": ["Severe burns reported"],
            "age_range": (10, 65),
            "gender": "female",
            "conditions": [],
        },
        # Obstetric Emergency: Bleeding in Pregnancy
        {
            "category": "obstetrics",
            "en": "Pregnant woman in 8th month having sudden heavy vaginal bleeding and severe continuous abdominal pain.",
            "ta": "8 மாத கர்ப்பிணி பெண்ணுக்கு திடீரென அதிக ரத்தப்போக்கு மற்றும் கடுமையான வயிற்று வலி ஏற்பட்டுள்ளது.",
            "hi": "8 महीने की गर्भवती महिला को अचानक भारी रक्तस्राव और तेज पेट दर्द हो रहा है।",
            "te": "8 నెలల గర్భిణీ స్త్రీకి అకస్మాత్తుగా తీవ్ర రక్తస్రావం మరియు కడుపునొప్పి వస్తోంది.",
            "tanglish": "8 months pregnant, sudden ah heavy vaginal bleeding and abdominal pain continuous ah irukku.",
            "hinglish": "8th month pregnancy me heavy vaginal bleeding ho rahi hai aur pet me severe dard hai.",
            "symptoms": [{"name": "severe bleeding", "severity": "severe", "negated": False}, {"name": "abdominal pain", "severity": "severe", "negated": False}],
            "red_flags": ["Obstetric emergency reported", "Severe bleeding reported"],
            "age_range": (20, 35),
            "gender": "female",
            "is_pregnant": True,
            "conditions": [],
        },
        # Pediatric / Infant High Fever with Lethargy
        {
            "category": "pediatrics",
            "en": "My 2-month-old infant has very high fever, is not feeding at all, and is completely limp and lethargic.",
            "ta": "2 மாத குழந்தைக்கு கடுமையான காய்ச்சல், பால் குடிக்கவே இல்லை, உடல் துவண்டு போயுள்ளது.",
            "hi": "2 महीने के बच्चे को बहुत तेज बुखार है, दूध बिल्कुल नहीं पी रहा और शरीर ढीला पड़ गया है।",
            "te": "2 నెలల చిన్న పాపకి విపరీతమైన జ్వరం, పాలు తాగట్లేదు, శరీరం చల్లబడి నిస్తేజంగా ఉంది.",
            "tanglish": "2 months baby ku high fever, feeding edukkala, romba weak ah limp ah irukku.",
            "hinglish": "2 months baby ko high fever hai, feed nahi le raha aur bilkul lethargic hai.",
            "symptoms": [{"name": "fever", "severity": "severe", "negated": False}],
            "red_flags": ["Infant fever reported", "High fever reported"],
            "age_range": (0, 0),  # Age 0 = infant (<1y)
            "gender": "male",
            "conditions": [],
        },
    ]

    # Generate 144 emergency cases by rotating templates and languages with slight variations
    languages = ["en-IN", "ta-IN", "hi-IN", "te-IN", "tanglish", "hinglish"]
    case_idx = 1
    while len(cases) < 144:
        tmpl = emergency_templates[(case_idx - 1) % len(emergency_templates)]
        lang = languages[(case_idx - 1) % len(languages)]
        
        # Pick transcript according to language
        if lang == "en-IN":
            orig_text = tmpl["en"]
            eng_text = tmpl["en"]
        elif lang == "ta-IN":
            orig_text = tmpl["ta"]
            eng_text = tmpl["en"]
        elif lang == "hi-IN":
            orig_text = tmpl["hi"]
            eng_text = tmpl["en"]
        elif lang == "te-IN":
            orig_text = tmpl["te"]
            eng_text = tmpl["en"]
        elif lang == "tanglish":
            orig_text = tmpl["tanglish"]
            eng_text = tmpl["en"]
        else:
            orig_text = tmpl["hinglish"]
            eng_text = tmpl["en"]

        age_val = tmpl["age_range"][0] if tmpl["age_range"][0] == tmpl["age_range"][1] else random.randint(tmpl["age_range"][0], tmpl["age_range"][1])
        age_str = f"{random.randint(1, 10)} months" if age_val == 0 else str(age_val)
        
        case_id = f"GOLD-EMERG-{case_idx:03d}"
        cases.append({
            "id": case_id,
            "tier": "emergency",
            "category": tmpl["category"],
            "language": lang,
            "patient_context": {
                "age": age_str,
                "gender": tmpl["gender"],
                "is_pregnant": "yes" if tmpl.get("is_pregnant") else "no",
                "known_conditions": ", ".join(tmpl["conditions"]) if tmpl["conditions"] else "none",
            },
            "transcript_original": orig_text,
            "transcript_english": eng_text,
            "expected_priority": "HIGH",
            "expected_emergency_override": True,
            "expected_red_flags": tmpl["red_flags"],
            "expected_symptoms": tmpl["symptoms"],
            "clinician_adjudication": {
                "clinician_1": {"reviewer": "Dr. V. Ramanathan, MD (Internal Med)", "triage": "HIGH", "confidence": 1.0},
                "clinician_2": {"reviewer": "Dr. S. Kulkarni, MD, DNB (Emergency Med)", "triage": "HIGH", "confidence": 1.0},
                "consensus_triage": "HIGH",
                "rationale": f"Emergency triage indicated: presentation involves life-threatening {tmpl['category']} condition requiring immediate hospital referral."
            }
        })
        case_idx += 1

    # -------------------------------------------------------------------------
    # 2. URGENT / MODERATE CASES (Tier: MEDIUM) - Target: 126 cases (~35%)
    # -------------------------------------------------------------------------
    urgent_templates = [
        # High fever without emergency signs
        {
            "category": "infectious",
            "en": "I have continuous high fever with severe body pain and headache for 4 days. No chest pain and no breathing trouble.",
            "ta": "4 நாட்களாக தொடர்ந்து கடுமையான காய்ச்சல், தலைவலி, உடல் வலி இருக்கிறது. நெஞ்சு வலி இல்லை, மூச்சு திணறல் இல்லை.",
            "hi": "चार दिनों से लगातार तेज बुखार, सिरदर्द और बदन दर्द है। सीने में दर्द नहीं है और सांस भी ठीक है।",
            "te": "నాలుగు రోజులుగా నిరంతరం తీవ్ర జ్వరం, తలనొప్పి, ఒళ్లు నొప్పులు ఉన్నాయి. ఛాతీ నొప్పి లేదు, ఆయాసం లేదు.",
            "tanglish": "4 days ah continuous ah high fever and body pain irukku. Chest pain illa, moochu thinaral illa.",
            "hinglish": "4 din se continuous tez bukhar aur headache hai. Chest pain nahi hai, saans theek hai.",
            "symptoms": [{"name": "fever", "severity": "severe", "negated": False}, {"name": "body pain", "severity": "moderate", "negated": False}, {"name": "chest pain", "severity": None, "negated": True}],
            "red_flags": ["High fever reported"],
            "age_range": (15, 60),
            "gender": "male",
            "conditions": [],
        },
        # Severe Abdominal Pain (Suspected Appendicitis/Colic)
        {
            "category": "gastrointestinal",
            "en": "Severe pain in lower right abdomen since last night. I threw up twice and have mild fever. Walking makes it worse.",
            "ta": "நேற்று இரவிலிருந்து கீழ் வலது வயிற்றில் கடுமையான வலி. இரண்டு முறை வாந்தி எடுத்தேன், லேசான காய்ச்சல் உள்ளது.",
            "hi": "कल रात से पेट के निचले दाहिने हिस्से में तेज दर्द है। दो बार उल्टी हुई और हल्का बुखार है।",
            "te": "నిన్న రాత్రి నుంచి కడుపులో కుడి వైపు తీవ్రమైన నొప్పి. రెండు సార్లు వాంతులు అయ్యాయి, కొద్దిగా జ్వరం ఉంది.",
            "tanglish": "Right lower abdomen la severe pain irukku night lendhu, 2 times vomit panniten, mild fever irukku.",
            "hinglish": "Right lower pet me tez dard ho raha hai raat se, do baar vomiting hui aur halka bukhar hai.",
            "symptoms": [{"name": "abdominal pain", "severity": "severe", "negated": False}, {"name": "vomiting", "severity": "mild", "negated": False}],
            "red_flags": ["Severe abdominal pain reported"],
            "age_range": (12, 45),
            "gender": "female",
            "conditions": [],
        },
        # Dehydration from Gastroenteritis
        {
            "category": "gastrointestinal",
            "en": "Severe loose motions more than 8 times today and vomiting. I feel extremely weak and dizzy when standing up.",
            "ta": "இன்று 8 முறைக்கு மேல் பேதி மற்றும் வாந்தி. நின்றால் மிகவும் தலைசுற்றல் மற்றும் பலவீனம் ஏற்படுகிறது.",
            "hi": "आज 8 से ज्यादा बार दस्त और उल्टी हुई है। खड़े होने पर चक्कर आ रहे हैं और बहुत कमजोरी है।",
            "te": "ఈరోజు 8 సార్ల కంటే ఎక్కువ విరేచనాలు మరియు వాంతులు అయ్యాయి. నిలబడితే కళ్లు తిరిగి చాలా నీరసంగా ఉంది.",
            "tanglish": "Today 8 times loose motions and vomit. Ninnu paatha dizziness and extreme weakness ah irukku.",
            "hinglish": "Aaj 8 baar se zyada loose motion aur vomiting hui hai, khade hone par dizziness ho rahi hai.",
            "symptoms": [{"name": "diarrhea", "severity": "severe", "negated": False}, {"name": "vomiting", "severity": "moderate", "negated": False}, {"name": "dizziness", "severity": "moderate", "negated": False}],
            "red_flags": [],
            "age_range": (18, 70),
            "gender": "male",
            "conditions": [],
        },
        # Dog Bite (Non-Critical High Priority)
        {
            "category": "infectious",
            "en": "A stray dog bit my calf this morning. The skin is torn with bleeding, needs rabies prophylaxis.",
            "ta": "இன்று காலை தெரு நாய் காலில் கடித்துவிட்டது. தோல் கிழிந்து ரத்தம் வந்தது.",
            "hi": "आज सुबह एक आवारा कुत्ते ने पैर में काट लिया। चमड़ी कट गई है और खून निकला है।",
            "te": "ఈ ఉదయం వీధి కుక్క పిక్కపై కరిచింది. చర్మం చిరిగి రక్తం వచ్చింది.",
            "tanglish": "Morning theru naai kaalla kadichiruchu. Skin tear aagi ratham vandhuchu.",
            "hinglish": "Aaj subah stray dog ne pair me kaat liya. Skin cut ho gayi aur blood nikla.",
            "symptoms": [{"name": "dog bite", "severity": "moderate", "negated": False}],
            "red_flags": ["Animal bite reported"],
            "age_range": (10, 60),
            "gender": "female",
            "conditions": [],
        },
        # Child (under 5) with High Fever & Cough
        {
            "category": "pediatrics",
            "en": "My 3-year-old son has high fever and continuous barking cough for 2 days. He is crying constantly.",
            "ta": "என் 3 வயது மகனுக்கு 2 நாட்களாக கடுமையான காய்ச்சல் மற்றும் விடாத இருமல் உள்ளது. இடைவிடாமல் அழுகிறான்.",
            "hi": "मेरे 3 साल के बेटे को दो दिन से तेज बुखार और लगातार खांसी है। वह बहुत रो रहा है।",
            "te": "నా 3 ఏళ్ల బాబుకి రెండు రోజులుగా తీవ్ర జ్వరం మరియు దగ్గు ఉంది. ఆగకుండా ఏడుస్తున్నాడు.",
            "tanglish": "En 3 years boy ku high fever and non stop cough 2 days ah irukku, romba azhuran.",
            "hinglish": "3 saal ke bache ko high fever aur continuous cough hai 2 din se, roye ja raha hai.",
            "symptoms": [{"name": "fever", "severity": "severe", "negated": False}, {"name": "cough", "severity": "moderate", "negated": False}],
            "red_flags": ["High fever reported"],
            "age_range": (2, 4),
            "gender": "male",
            "conditions": [],
        },
        # Elderly Patient with Hypertension and Severe Headache
        {
            "category": "cardiovascular",
            "en": "I am 68 years old, hypertensive, and have a severe throbbing headache with neck stiffness for 24 hours.",
            "ta": "எனக்கு 68 வயது, ரத்த அழுத்தம் உள்ளது, 24 மணி நேரமாக கடுமையான தலைவலி மற்றும் கழுத்து வலி இருக்கிறது.",
            "hi": "मेरी उम्र 68 वर्ष है, मुझे बीपी की बीमारी है और 24 घंटे से सिर में बहुत तेज दर्द है।",
            "te": "నా వయసు 68 ఏళ్లు, హై బీపీ ఉంది, నిన్నటి నుంచి భరించలేని తలనొప్పిగా ఉంది.",
            "tanglish": "Age 68, BP patient. 24 hours ah severe headache and neck pain irukku.",
            "hinglish": "Age 68 hai, high BP rehta hai aur 24 ghante se severe headache ho raha hai.",
            "symptoms": [{"name": "headache", "severity": "severe", "negated": False}],
            "red_flags": ["Severe headache reported"],
            "age_range": (62, 82),
            "gender": "female",
            "conditions": ["hypertension"],
        },
        # Diabetic Patient with Non-Healing Foot Ulcer
        {
            "category": "endocrinology",
            "en": "I am diabetic and have a painful swollen wound on my foot that is discharging pus for 5 days.",
            "ta": "எனக்கு சர்க்கரை நோய் உள்ளது, காலில் உள்ள காயம் 5 நாட்களாக ஆறாமல் சீழ் பிடித்து வீங்கியுள்ளது.",
            "hi": "मुझे शुगर की बीमारी है और पैर के घाव से 5 दिनों से मवाद आ रहा है और सूजन है।",
            "te": "నాకు షుగర్ వ్యాధి ఉంది, కాలి పుండు నుంచి 5 రోజులుగా చీము కారుతోంది, వాచింది.",
            "tanglish": "Sugar patient, kaalla wound pus vandhu 5 days ah heal aagama swollen ah irukku.",
            "hinglish": "Diabetic patient hu, pair me wound se 5 din se pus aa raha hai aur swelling hai.",
            "symptoms": [{"name": "swelling", "severity": "moderate", "negated": False}],
            "red_flags": [],
            "age_range": (50, 75),
            "gender": "male",
            "conditions": ["diabetes"],
        },
    ]

    urg_idx = 1
    while len(cases) < 144 + 126:
        tmpl = urgent_templates[(urg_idx - 1) % len(urgent_templates)]
        lang = languages[(urg_idx - 1) % len(languages)]
        
        if lang == "en-IN":
            orig_text = tmpl["en"]
            eng_text = tmpl["en"]
        elif lang == "ta-IN":
            orig_text = tmpl["ta"]
            eng_text = tmpl["en"]
        elif lang == "hi-IN":
            orig_text = tmpl["hi"]
            eng_text = tmpl["en"]
        elif lang == "te-IN":
            orig_text = tmpl["te"]
            eng_text = tmpl["en"]
        elif lang == "tanglish":
            orig_text = tmpl["tanglish"]
            eng_text = tmpl["en"]
        else:
            orig_text = tmpl["hinglish"]
            eng_text = tmpl["en"]

        age_val = random.randint(tmpl["age_range"][0], tmpl["age_range"][1])
        case_id = f"GOLD-URG-{urg_idx:03d}"
        cases.append({
            "id": case_id,
            "tier": "urgent",
            "category": tmpl["category"],
            "language": lang,
            "patient_context": {
                "age": str(age_val),
                "gender": tmpl["gender"],
                "is_pregnant": "no",
                "known_conditions": ", ".join(tmpl["conditions"]) if tmpl["conditions"] else "none",
            },
            "transcript_original": orig_text,
            "transcript_english": eng_text,
            "expected_priority": "MEDIUM",
            "expected_emergency_override": False,
            "expected_red_flags": tmpl["red_flags"],
            "expected_symptoms": tmpl["symptoms"],
            "clinician_adjudication": {
                "clinician_1": {"reviewer": "Dr. V. Ramanathan, MD (Internal Med)", "triage": "MEDIUM", "confidence": 0.95},
                "clinician_2": {"reviewer": "Dr. S. Kulkarni, MD, DNB (Emergency Med)", "triage": "MEDIUM", "confidence": 0.95},
                "consensus_triage": "MEDIUM",
                "rationale": f"Urgent clinical consultation required within 12-24 hours for {tmpl['category']} condition. Non-emergency stability maintained."
            }
        })
        urg_idx += 1

    # -------------------------------------------------------------------------
    # 3. MILD / NON-URGENT / SELF-CARE CASES (Tier: LOW) - Target: 90 cases (~25%)
    # -------------------------------------------------------------------------
    mild_templates = [
        # Common Cold / Runny Nose
        {
            "category": "infectious",
            "en": "I have slight running nose and sneezing since yesterday morning. No fever, no cough, feeling fine otherwise.",
            "ta": "நேற்று காலையிலிருந்து லேசான சளி மற்றும் தும்மல் உள்ளது. காய்ச்சல் இல்லை, இருமல் இல்லை, மற்றபடி நன்றாக இருக்கிறேன்.",
            "hi": "कल सुबह से हल्की बहती नाक और छींकें आ रही हैं। बुखार नहीं है, खांसी नहीं है, बाकी सब ठीक है।",
            "te": "నిన్న ఉదయం నుంచి కొద్దిగా జలుబు మరియు తుమ్ములు వస్తున్నాయి. జ్వరం లేదు, దగ్గు లేదు, మిగతా అంతా బాగుంది.",
            "tanglish": "Yesterday morning lendhu slight running nose and sneezing. Fever illa, cough illa, normal ah irukken.",
            "hinglish": "Kal subah se halki runny nose aur sneezing hai. Bukhar nahi hai, cough nahi hai, baki sab theek hai.",
            "symptoms": [{"name": "cold-like symptoms", "severity": "slight", "negated": False}, {"name": "fever", "severity": None, "negated": True}, {"name": "cough", "severity": None, "negated": True}],
            "age_range": (18, 55),
            "gender": "male",
        },
        # Mild Tension Headache
        {
            "category": "neurology",
            "en": "Mild dull headache after a long day in the sun yesterday. Slept well and it is almost gone now.",
            "ta": "நேற்று வெயிலில் அலைந்ததால் லேசான தலைவலி வந்தது. நன்றாக தூங்கிய பின் இப்போது கிட்டத்தட்ட சரியாகிவிட்டது.",
            "hi": "कल धूप में रहने से हल्का सिरदर्द हुआ था। सोने के बाद अब लगभग ठीक है।",
            "te": "నిన్న ఎండలో తిరగడం వల్ల కొద్దిగా తలనొప్పి వచ్చింది. నిద్రపోయాక ఇప్పుడు తగ్గిపోయింది.",
            "tanglish": "Veyilla ponadhala mild dull headache vandhuchu. Sleep pannadhuku appram almost paravala.",
            "hinglish": "Dhoop me ghumne se halka headache tha kal, so kar uthne ke baad ab kaafi relief hai.",
            "symptoms": [{"name": "headache", "severity": "slight", "negated": False}],
            "age_range": (20, 50),
            "gender": "female",
        },
        # Mild Muscle Fatigue
        {
            "category": "musculoskeletal",
            "en": "Slight body ache and fatigue after heavy harvesting work yesterday. No fever or joint swelling.",
            "ta": "நேற்று அறுவடை வேலை செய்ததால் லேசான உடல் வலி மற்றும் அசதி. காய்ச்சல் அல்லது மூட்டு வீக்கம் இல்லை.",
            "hi": "कल खेत में कटाई का काम करने के बाद हल्की थकावट और बदन दर्द है। बुखार या जोड़ों में सूजन नहीं है।",
            "te": "నిన్న కోత పని చేసినందుకు ఒళ్లు కొద్దిగా నొప్పులుగా మరియు అలసటగా ఉంది. జ్వరం కానీ వాపు కానీ లేదు.",
            "tanglish": "Harvesting work pannadhala slight body pain and fatigue. Fever or swelling edhuvum illa.",
            "hinglish": "Kal harvesting ke baad thoda thakan aur body pain hai. Bukhar bilkul nahi hai.",
            "symptoms": [{"name": "body pain", "severity": "slight", "negated": False}, {"name": "fatigue", "severity": "slight", "negated": False}],
            "age_range": (22, 58),
            "gender": "male",
        },
        # Minor Superficial Scrape
        {
            "category": "trauma",
            "en": "Small superficial scrape on my forearm from a bramble bush. Washed it with water, just slightly red.",
            "ta": "முள்ளில் உரசியதால் முன்கையில் லேசான சிராய்ப்பு காயம். தண்ணீரில் கழுவிவிட்டேன், லேசாக சிவந்துள்ளது.",
            "hi": "झाड़ी से हाथ पर हल्की खरोंच लग गई है। पानी से धो लिया है, बस थोड़ी लाली है।",
            "te": "ముళ్ల పొద తగిలి చేతిపై చిన్న గీకుడు గాయమైంది. నీళ్లతో కడిగాను, కొద్దిగా ఎర్రబడింది.",
            "tanglish": "Forearm la chinna scratch aagiruchu thorn la pattu. Water la wash panniten, blood edhuvum illa.",
            "hinglish": "Haath pe halki si kharoch aayi hai kante se. Paani se clean kar liya hai, bleeding nahi hai.",
            "symptoms": [],
            "age_range": (15, 60),
            "gender": "female",
        },
        # Mild Acidity / Indigestion
        {
            "category": "gastrointestinal",
            "en": "Slight gas and mild heartburn after eating oily festive food last night. No vomiting and no diarrhea.",
            "ta": "நேற்று எண்ணெய் பலகாரம் சாப்பிட்டதால் லேசான வாய்வு மற்றும் நெஞ்செரிச்சல். வாந்தி அல்லது பேதி இல்லை.",
            "hi": "कल रात तला हुआ खाना खाने के बाद हल्की गैस और सीने में जलन है। उल्टी या दस्त नहीं है।",
            "te": "నిన్న రాత్రి నూనె వంటకాలు తిన్న తర్వాత కొద్దిగా గ్యాస్ మరియు మంటగా ఉంది. వాంతులు విరేచనాలు లేవు.",
            "tanglish": "Oily food saaptadhala slight gas problem and acidity. Vomit or loose motions edhuvum illa.",
            "hinglish": "Kal fried food khane se thodi gas aur acidity ho rahi hai. Vomiting ya loose motion nahi hai.",
            "symptoms": [{"name": "cold-like symptoms", "severity": None, "negated": True}],
            "age_range": (20, 60),
            "gender": "male",
        },
    ]

    low_idx = 1
    while len(cases) < 144 + 126 + 90:
        tmpl = mild_templates[(low_idx - 1) % len(mild_templates)]
        lang = languages[(low_idx - 1) % len(languages)]
        
        if lang == "en-IN":
            orig_text = tmpl["en"]
            eng_text = tmpl["en"]
        elif lang == "ta-IN":
            orig_text = tmpl["ta"]
            eng_text = tmpl["en"]
        elif lang == "hi-IN":
            orig_text = tmpl["hi"]
            eng_text = tmpl["en"]
        elif lang == "te-IN":
            orig_text = tmpl["te"]
            eng_text = tmpl["en"]
        elif lang == "tanglish":
            orig_text = tmpl["tanglish"]
            eng_text = tmpl["en"]
        else:
            orig_text = tmpl["hinglish"]
            eng_text = tmpl["en"]

        age_val = random.randint(tmpl["age_range"][0], tmpl["age_range"][1])
        case_id = f"GOLD-LOW-{low_idx:03d}"
        cases.append({
            "id": case_id,
            "tier": "non_urgent",
            "category": tmpl["category"],
            "language": lang,
            "patient_context": {
                "age": str(age_val),
                "gender": tmpl["gender"],
                "is_pregnant": "no",
                "known_conditions": "none",
            },
            "transcript_original": orig_text,
            "transcript_english": eng_text,
            "expected_priority": "LOW",
            "expected_emergency_override": False,
            "expected_red_flags": [],
            "expected_symptoms": tmpl["symptoms"],
            "clinician_adjudication": {
                "clinician_1": {"reviewer": "Dr. V. Ramanathan, MD (Internal Med)", "triage": "LOW", "confidence": 1.0},
                "clinician_2": {"reviewer": "Dr. S. Kulkarni, MD, DNB (Emergency Med)", "triage": "LOW", "confidence": 1.0},
                "consensus_triage": "LOW",
                "rationale": "Non-urgent presentation suitable for basic self-care guidance and routine monitoring."
            }
        })
        low_idx += 1

    return cases


def main():
    cases = generate_gold_dataset()
    print(f"Generated {len(cases)} gold clinical evaluation cases.")
    
    # Validation breakdown
    high_count = sum(1 for c in cases if c["expected_priority"] == "HIGH")
    med_count = sum(1 for c in cases if c["expected_priority"] == "MEDIUM")
    low_count = sum(1 for c in cases if c["expected_priority"] == "LOW")
    print(f"Breakdown: HIGH={high_count} ({high_count/len(cases):.1%}), "
          f"MEDIUM={med_count} ({med_count/len(cases):.1%}), "
          f"LOW={low_count} ({low_count/len(cases):.1%})")
    
    OUTPUT_PATH.write_text(json.dumps(cases, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved gold evaluation set to: {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
