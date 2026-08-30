# RuralCare AI — Day 1: Core Pipeline

```
Voice → Sarvam Saaras (STT) → Gemini (structured extraction) → JSON
```

No UI, no database, no auth yet — just the vertical slice that proves the
core idea works. Everything downstream (Day 2 priority engine, Day 3
dashboards) calls `app/pipeline.py:run_pipeline()`.

## What's included

| File | Role |
|---|---|
| `app/config.py` | Loads `SARVAM_API_KEY` / `GEMINI_API_KEY` from `.env` |
| `app/schemas.py` | `StructuredMedicalSummary` — the forced JSON schema. No diagnosis field, by design. |
| `app/services/sarvam_stt.py` | Calls Sarvam `/speech-to-text` (native transcript + English translation) |
| `app/services/gemini_extract.py` | Calls Gemini with `response_schema=StructuredMedicalSummary`, extraction-only prompt |
| `app/pipeline.py` | Orchestrates STT → extraction, returns `PipelineResult` |
| `app/main.py` | One FastAPI route: `POST /api/v1/pipeline/process-audio` |
| `scripts/test_pipeline.py` | CLI to test the pipeline with a local audio file — no server needed |

## Setup

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in SARVAM_API_KEY and GEMINI_API_KEY
```

## Test the pipeline directly (fastest way to check Day 1 works)

```bash
python scripts/test_pipeline.py path/to/sample.wav --language ta-IN
```

This prints the native transcript, English transcript, and the structured
JSON — no frontend, no HTTP server required.

## Or run it as an API

```bash
uvicorn app.main:app --reload --port 8000
```

Then:

```bash
curl -X POST http://localhost:8000/api/v1/pipeline/process-audio \
  -F "audio=@sample.wav" \
  -F "language_code=ta-IN"
```

Check `GET /health` first to confirm both API keys are loaded.
Interactive docs at `http://localhost:8000/docs`.

## Design notes for later days

- **Provider isolation**: only `sarvam_stt.py` knows Sarvam's request/response
  shape. Swapping in Whisper/IndicConformer later means rewriting this one
  file, not the pipeline.
- **No diagnosis, anywhere**: Gemini's system prompt forbids naming a
  condition. `red_flags` captures only what the patient explicitly said —
  Day 2's rule engine + Logistic Regression model decides priority from
  these fields, not Gemini.
- **Both transcripts are kept**: native-language + English, so a doctor can
  later verify the AI didn't misunderstand the patient.
- **Secrets**: only ever read via `app/config.py` from environment
  variables. Never hardcode or log API keys or raw patient audio/transcripts.
