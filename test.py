from google import genai
import os
from dotenv import load_dotenv

load_dotenv()

# ✅ Test all your keys and show available models for each
API_KEYS = {
    "Key 1": os.getenv("GEMINI_API_KEY_1"),
    "Key 2": os.getenv("GEMINI_API_KEY_2"),
    "Key 3": os.getenv("GEMINI_API_KEY_3"),
}

for key_name, api_key in API_KEYS.items():
    if not api_key:
        print(f"\n❌ {key_name}: Not found in .env")
        continue

    print(f"\n{'='*50}")
    print(f"🔑 {key_name}: {api_key[:10]}...")
    print(f"{'='*50}")

    try:
        client = genai.Client(api_key=api_key)
        models = client.models.list()

        print(f"✅ Available Models:")
        for model in models:
            if "generateContent" in (model.supported_actions or []):
                print(f"   - {model.name}")

    except Exception as e:
        print(f"❌ Error with {key_name}: {str(e)}")

print("\n✅ Done checking all keys!")