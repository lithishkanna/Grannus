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
    parser = argparse.ArgumentParser(description="Run the RuralCare AI Day 1 pipeline on a local audio file.")
    parser.add_argument("audio_path", type=Path, help="Path to a WAV/MP3/etc. audio file")
    parser.add_argument("--language", default="unknown", help="BCP-47 code, e.g. ta-IN, hi-IN (default: auto-detect)")
    args = parser.parse_args()

    if not args.audio_path.exists():
        print(f"File not found: {args.audio_path}", file=sys.stderr)
        sys.exit(1)

    audio_bytes = args.audio_path.read_bytes()

    result = await run_pipeline(
        audio_bytes=audio_bytes,
        filename=args.audio_path.name,
        language_code=args.language,
        patient_context={},  # no extra form context in this quick test
    )

    print("\n=== TRANSCRIPTION ===")
    print(f"Language     : {result.transcription.language_code}")
    print(f"Native text  : {result.transcription.transcript_original}")
    print(f"English text : {result.transcription.transcript_english}")

    print("\n=== STRUCTURED CLINICAL SUMMARY ===")
    print(json.dumps(result.structured_summary.model_dump(), indent=2, ensure_ascii=False))

    print("\n=== PRIORITY (separate rule engine, not Gemini) ===")
    print(f"Level              : {result.priority.level}")
    print(f"Emergency override : {result.priority.emergency_override}")
    print(f"Triggered rules    : {result.priority.triggered_rules}")
    print(f"Reason             : {result.priority.reason}")

    print("\n=== MISSING INFORMATION / NEXT QUESTION ===")
    for item in result.missing_information:
        print(f"  [{item.priority}] {item.field}: {item.question}")
    print(f"Next follow-up question to ask: {result.next_follow_up_question}")

    print("\n=== FULL PIPELINE RESULT (what the API returns) ===")
    print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
