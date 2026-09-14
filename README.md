# Grannus 

> **Bridging the healthcare and language gap between rural patients and urban doctors in India.**

Grannus  is a multilingual, voice-first triage platform. Our mission is simple: allow rural patients to explain their symptoms naturally in their native regional language, and instantly provide urban doctors with structured, English-translated, medically-accurate summaries. 

By combining cutting-edge speech-to-text, LLM-based medical extraction, safety red-flag screening, and a beautiful, calming "Wabi-Sabi" user interface, Grannus brings world-class healthcare triage to the most remote areas.

---

## 🌟 What Makes Grannus Unique

### 🫁 Acoustic Biomarker Analysis
Unlike any other triage platform, Grannus doesn't just listen to *what* the patient says — it analyzes *how* they sound. Using real-time signal processing on the raw audio waveform, we detect:
- **Cough frequency** — explosive energy bursts in the audio
- **Wheezing patterns** — sustained narrow-band energy in the 100–500Hz range
- **Breathlessness pauses** — speech gaps indicating respiratory distress

Even if a patient forgets to mention "I have a cough", the system will flag respiratory distress automatically from the audio alone.

### 🔄 Bidirectional Voice Prescriber
Most telemedicine tools only go one way: patient → doctor. Grannus closes the loop:
1. The patient speaks in their dialect → AI generates an English summary for the doctor
2. The doctor records advice in English → AI translates it back into the patient's native language and generates a **spoken voice note**

This means an illiterate rural patient receives medical advice as a clear audio message in their own language — not an English PDF they can't read.

### 📋 ABDM FHIR Bundling
Grannus automatically converts every triage session into an **HL7 FHIR R4** compliant JSON bundle, ready for India's Ayushman Bharat Digital Mission (ABDM). Doctors can export patient data with one click and plug it directly into any ABDM-certified hospital EMR system.

---

## 🔄 Core Pipeline

```text
Patient Voice Input
       │
       ▼
Audio Preprocessing (Noise Reduction)
       │
       ├──► Acoustic Biomarker Analysis (Cough/Wheeze/Breathlessness)
       │
       ▼
Sarvam Speech-to-Text (Native + English Translation)
       │
       ▼
Medical Information Extraction (Gemini LLM)
       │
       ▼
Safety / Red-Flag Screening & Missing Info Detection
       │
       ▼
Feature Extraction & Priority Classification Engine
       │
       ▼
Doctor Review Dashboard Ready Output
       │
       ├──► Doctor Voice Reply → Translated Voice Note for Patient
       └──► ABDM FHIR Export
```

---

## 🛠️ Technology Stack

### Frontend
- **Framework**: Next.js 15 (React 19)
- **Styling**: Tailwind CSS v4 + custom organic Wabi-Sabi design tokens
- **UI Components**: shadcn/ui, Radix UI, Framer Motion for fluid animations
- **Icons**: Lucide React

### Backend (AI Pipeline)
- **Framework**: FastAPI (Python 3.10+)
- **AI / LLMs**: Google Gemini API (Extraction & Translation), Sarvam AI (Indic STT & TTS)
- **ML & Audio**: Scikit-Learn (Triage Model), noisereduce, SciPy, NumPy
- **Signal Processing**: Custom acoustic biomarker detection engine

### Database
- **Provider**: Supabase (PostgreSQL)
- **Standards**: ABDM-ready, FHIR R4 export capability

---

## 🚀 Getting Started

### 1. Database Setup (Supabase)
Ensure your Supabase project has the required tables (`consultations`, `pipeline_results`, `clinical_summaries`, `symptoms`, `safety_assessments`, `priority_assessments`, `follow_up_questions`).

### 2. Backend Setup (FastAPI)
```bash
cd backend
python -m venv venv
# Windows: .\venv\Scripts\activate
# Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
```
Create a `.env` file in the `backend/` directory:
```env
SARVAM_API_KEY=your_sarvam_key
GEMINI_API_KEY=your_gemini_key
GEMINI_MODEL=gemini-3.6-flash
```
Start the backend server:
```bash
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend Setup (Next.js)
```bash
cd frontend
npm install
```
Create a `.env.local` file in the `frontend/` directory:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=your_supabase_url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key
```
Start the development server:
```bash
npm run dev
```
Navigate to `http://localhost:3000` to experience Grannus!

---

## 📜 License
Distributed under the MIT License. See `LICENSE` for details.
