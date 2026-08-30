# Grannus — RuralCare AI

> **Bridging the healthcare & language gap between rural patients and urban doctors.**

Grannus (RuralCare AI) is a multilingual, voice-first rural healthcare communication platform designed to solve the communication gap between rural patients and urban doctors in India. It preprocesses rural patient voice inputs in regional Indic languages, extracts structured medical summaries using LLMs, detects safety red-flags, and classifies patient triage priority levels.

---

## 🔄 Core Flow

```text
Patient Voice Input
       │
       ▼
Audio Preprocessing (Noise Reduction)
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
```

---

## 🌟 Key Features

- **Indian-Language Voice Input**: High-accuracy Indic speech recognition via Sarvam Saaras STT.
- **Background Noise Reduction**: Preprocessing tailored for recordings from low-cost mobile devices.
- **Structured Clinical Extraction**: Powered by Gemini API to produce standardized medical JSON summaries without diagnostic hallucination.
- **Safety & Red-Flag Screening**: Automated clinical red-flag evaluation and missing details identifier.
- **Explainable Priority Classification**: Hybrid priority classification combining clinical rules and scikit-learn models.
- **Multilingual Support**: Keeps both native transcripts and translated English outputs for verification.
- **FastAPI Backend**: Clean modular REST API serving end-to-end processing pipelines.

---

## 🛠️ Tech Stack

- **Core**: Python 3.10+, FastAPI, Uvicorn, Pydantic
- **AI / Speech / LLM**: Sarvam AI (Saaras STT), Google Gemini API
- **ML & Signal Processing**: Scikit-Learn, Joblib, SciPy, noisereduce, soundfile
- **Data Models**: Pydantic schemas, SQLite

---

## 📂 Project Structure

```text
├── backend/
│   ├── app/
│   │   ├── main.py                     # FastAPI application entrypoint
│   │   ├── pipeline.py                 # Core orchestration pipeline
│   │   ├── schemas.py                  # Pydantic JSON schemas
│   │   ├── priority.py                 # Triage priority calculation engine
│   │   ├── ml_model.py                 # ML Priority model wrapper
│   │   ├── safety.py                   # Safety & red flag guardrails
│   │   ├── audio_preprocessing.py      # Audio processing tools
│   │   ├── missing_info.py             # Identifies missing clinical details
│   │   └── services/
│   │       ├── sarvam_stt.py           # Sarvam Speech-to-Text integration
│   │       ├── gemini_extract.py       # Gemini clinical summary extraction
│   │       └── translation.py          # Translation service helpers
│   ├── models/                         # Trained ML model weights
│   ├── scripts/                        # Model training and pipeline test scripts
│   ├── eval/                           # Evaluation benchmark data
│   ├── .env.example                    # Environment variable template
│   └── requirements.txt
├── .gitignore
├── IDEA.md
├── LICENSE
└── README.md
```

---

## 🚀 Quick Start

### 1. Setup Backend Environment

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `backend/.env` with your API credentials:
```env
SARVAM_API_KEY=your_sarvam_api_key
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-3.6-flash
```

### 2. Test the Pipeline via CLI

```bash
python scripts/test_pipeline.py path/to/sample.wav --language ta-IN
```

### 3. Run FastAPI Server

```bash
uvicorn app.main:app --reload --port 8000
```

Access Interactive API Documentation at: `http://localhost:8000/docs`

---

## 📜 License

Distributed under the MIT License. See [`LICENSE`](LICENSE) for details.
