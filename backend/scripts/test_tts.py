import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from app.config import get_settings

async def test_tts():
    settings = get_settings()
    url = f"{settings.sarvam_base_url}/text-to-speech"
    headers = {"api-subscription-key": settings.sarvam_api_key}
    
    payload = {
        "inputs": ["सर्दी जैसी लक्षणों वाला बुखार, सिरदर्द, अंगों में दर्द"],
        "target_language_code": "hi-IN",
        "speaker": "kavya",
        "pace": 1.0,
        "speech_sample_rate": 8000,
        "enable_preprocessing": True,
        "model": "bulbul:v3",
    }
    
    async with httpx.AsyncClient() as client:
        res = await client.post(url, json=payload, headers=headers)
        print("Status:", res.status_code)
        print("Response:", res.text[:500])

if __name__ == "__main__":
    asyncio.run(test_tts())
