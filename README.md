# Grannus — RuralCare AI

> **Bridging the healthcare and language gap between rural patients and urban doctors in India.**

Grannus (RuralCare AI) is a multilingual, voice-first triage platform. Our mission is simple: allow rural patients to explain their symptoms naturally in their native regional language, and instantly provide urban doctors with structured, English-translated, medically-accurate summaries. 

By combining cutting-edge speech-to-text, LLM-based medical extraction, safety red-flag screening, and a beautiful, calming "Wabi-Sabi" user interface, Grannus brings world-class healthcare triage to the most remote areas.

---

## 🌟 The Experience

We believe healthcare software shouldn't feel clinical and cold. Grannus is designed around the **Wabi-Sabi** aesthetic—embracing organic shapes, earthy stone tones, natural paper textures, and smooth micro-animations. The result is a calming, premium interface that reduces stress for both patients and healthcare workers.

### Core Pipeline
1. **Voice Input**: Patients record their symptoms via an intuitive audio interface.
2. **Audio Processing & STT**: Background noise is reduced, and Sarvam AI transcribes the regional language.
3. **Medical Extraction**: Gemini intelligently extracts the chief complaint, symptoms, and duration.
4. **Safety Guardrails**: Immediate detection of critical red flags (e.g., severe chest pain) to alert for emergency care.
5. **Priority Engine**: A hybrid ML model assigns a triage priority (High/Medium/Low).
6. **Doctor Dashboard**: All data flows seamlessly into a Supabase-powered dashboard for doctors to review the translated summaries.

---

## 🛠️ Technology Stack

We built Grannus using a modern, robust, and production-ready stack:

### Frontend
- **Framework**: Next.js 15 (React 19)
- **Styling**: Tailwind CSS v4 + custom organic Wabi-Sabi design tokens
- **UI Components**: shadcn/ui, Radix UI, Framer Motion for fluid animations
- **Icons**: Lucide React

### Backend (AI Pipeline)
- **Framework**: FastAPI (Python 3.10+)
- **AI / LLMs**: Google Gemini API (Extraction & Translation), Sarvam Saaras (Indic Speech-to-Text)
- **ML & Audio**: Scikit-Learn (Triage Model), noisereduce, SciPy

### Database
- **Provider**: Supabase (PostgreSQL)
- **Architecture**: Enforces strict schema validations and check constraints for clinical data integrity.

---

## 🚀 Getting Started

### 1. Database Setup (Supabase)
Ensure your Supabase project is set up with the required tables (`consultations`, `pipeline_results`, `clinical_summaries`, `symptoms`, `safety_assessments`, `priority_assessments`, `follow_up_questions`).

### 2. Backend Setup (FastAPI)
```bash
cd backend
python -m venv venv
# On Windows: .\venv\Scripts\activate
# On Mac/Linux: source venv/bin/activate
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
