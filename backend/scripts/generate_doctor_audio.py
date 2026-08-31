"""
Generates and saves the doctor's spoken voice audio in Hindi/Tamil to a .wav file.
Usage:
    python scripts/generate_doctor_audio.py "C:\\path\\to\\patient_audio.ogg" --lang hi-IN
"""
import argparse
import asyncio
import base64
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.pipeline import run_pipeline


async def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Generate doctor voice summary WAV file")
    parser.add_argument("audio_path", type=Path, help="Path to input audio file")
    parser.add_argument("--lang", default="hi-IN", help="Doctor preferred language (e.g., hi-IN, ta-IN)")
    args = parser.parse_args()

    if not args.audio_path.exists():
        print(f"Audio file not found: {args.audio_path}")
        return

    print(f"Processing audio '{args.audio_path.name}' with doctor language '{args.lang}'...")
    audio_bytes = args.audio_path.read_bytes()

    result = await run_pipeline(
        audio_bytes=audio_bytes,
        filename=args.audio_path.name,
        language_code="unknown",
        patient_context={},
        doctor_preferred_language=args.lang,
    )

    if not result.doctor_translated_summary or not result.doctor_translated_summary.audio_base64:
        print("No voice audio generated (check if priority is MEDIUM/HIGH and API keys are valid).")
        return

    # Decode base64 string to WAV file
    b64_str = result.doctor_translated_summary.audio_base64
    wav_bytes = base64.b64decode(b64_str)
    
    out_filename = f"doctor_summary_{args.lang.split('-')[0]}.wav"
    out_path = Path(__file__).resolve().parent.parent / out_filename
    out_path.write_bytes(wav_bytes)

    print(f"\nSUCCESS! Spoken doctor audio saved to: {out_path}")
    print(f"Hindi Text: {result.doctor_translated_summary.chief_complaint}")

    # Launch default Windows audio player
    try:
        os.startfile(str(out_path))
        print("Opening audio player...")
    except Exception as e:
        print(f"To listen, open file manually: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
