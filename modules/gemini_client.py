import os
from dotenv import load_dotenv

load_dotenv()

API_KEYS = [
    os.getenv("GEMINI_API_KEY_1"),
    os.getenv("GEMINI_API_KEY_2"),
    os.getenv("GEMINI_API_KEY_3"),
]

MODELS = [
    "gemini-2.0-flash",        # fast + reliable — start here
    "gemini-2.5-flash",        # best quality fallback
    "gemini-2.0-flash-lite",   # last resort (weakest)
]

MODEL_NAME = MODELS[0]
VALID_KEYS = [k for k in API_KEYS if k]


def get_client():
    from google import genai
    import random
    if not VALID_KEYS:
        raise ValueError("No Gemini API keys configured in .env")
    key = random.choice(VALID_KEYS)
    return genai.Client(api_key=key)