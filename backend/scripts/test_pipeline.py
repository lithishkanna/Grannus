"""
Day 1 smoke test — exercises the full pipeline with no UI and no server.

Usage:
    cd backend
    python scripts/test_pipeline.py path/to/audio.wav --language ta-IN

If --language is omitted, Sarvam will auto-detect the spoken language.
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # allow `import app.*`

from dotenv import load_dotenv

load_dotenv()

from app.pipeline import run_pipeline  # noqa: E402


async def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Run the RuralCare AI Day 1 pipeline on a local audio file.")
    parser.add_argument("audio_path", type=Path, help="Path to a WAV/MP3/etc. audio file")
    parser.add_argument("--language", default="unknown", help="BCP-47 code, e.g. ta-IN, hi-IN (default: auto-detect)")
    parser.add_argument("--doctor-language", default="en-IN", help="BCP-47 code for doctor's language e.g. ta-IN, hi-IN")
    args = parser.parse_args()

    if not args.audio_path.exists():
        print(f"File not found: {args.audio_path}", file=sys.stderr)
        sys.exit(1)

    audio_bytes = args.audio_path.read_bytes()

    result = await run_pipeline(
        audio_bytes=audio_bytes,
        filename=args.audio_path.name,
        language_code=args.language,
        patient_context={},
        doctor_preferred_language=args.doctor_language,
    )

    print("\n=== TRANSCRIPTION ===")
    print(f"Language     : {result.patient_input.language}")
    print(f"Native text  : {result.patient_input.transcript_original}")
    print(f"English text : {result.patient_input.transcript_english}")

    print("\n=== STRUCTURED CLINICAL SUMMARY ===")
    print(json.dumps(result.clinical_summary.model_dump(), indent=2, ensure_ascii=False))

    print("\n=== PRIORITY (separate rule engine, not Gemini) ===")
    print(f"Level              : {result.priority.level}")
    print(f"Emergency override : {result.priority.emergency_override}")
    print(f"Triggered rules    : {result.priority.triggered_rules}")
    print(f"Reasons            : {result.priority.reasons}")

    print("\n=== MISSING INFORMATION / FOLLOW-UP QUESTIONS ===")
    for item in result.safety_screening.missing_information:
        print(f"  [{item.priority}] {item.field}: {item.question}")
    print(f"Follow-up questions: {result.safety_screening.follow_up_questions}")

    if result.home_remedy_guidance:
        print("\n=== HOME REMEDY GUIDANCE (LOW priority) ===")
        for step in result.home_remedy_guidance.care_steps:
            print(f"  - {step.step}")
        print(f"  Seek doctor if: {result.home_remedy_guidance.seek_doctor_if}")

    if result.doctor_translated_summary:
        print("\n=== DOCTOR TRANSLATED SUMMARY & VOICE AUDIO ===")
        print(f"  Language       : {result.doctor_translated_summary.language}")
        print(f"  Chief complaint: {result.doctor_translated_summary.chief_complaint}")
        print(f"  Symptoms       : {result.doctor_translated_summary.symptoms_summary}")
        has_audio = bool(result.doctor_translated_summary.audio_base64)
        audio_len = len(result.doctor_translated_summary.audio_base64) if has_audio else 0
        print(f"  Spoken Audio   : {'Generated (' + str(audio_len) + ' base64 chars)' if has_audio else 'None'}")

    print("\n=== FULL PIPELINE RESULT (what the API returns) ===")
    print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
