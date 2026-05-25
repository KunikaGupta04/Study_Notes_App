import json
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def generate_quiz(notes):
    # Truncate to avoid exceeding token limits
    notes_trimmed = notes[:4000]

    prompt = f"""
    Based on these notes, generate exactly 10 multiple choice quiz questions.
    Notes: {notes_trimmed}

    Return ONLY a JSON object with a key "quiz" containing an array of exactly 10 questions.
    Each question must have:
    - "question": The question text (clear and specific).
    - "options": A list of exactly 4 strings (plausible options).
    - "answer": The exact string from options that is correct (must match options exactly).

    Example Format:
    {{
      "quiz": [
        {{
          "question": "What is AI?",
          "options": ["Artificial Intelligence", "Automated Input", "Advanced Interface", "Analog Integration"],
          "answer": "Artificial Intelligence"
        }}
      ]
    }}

    IMPORTANT: Return all 10 questions. Do not stop early.
    """

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=3000,
            temperature=0.7
        )
        content = response.choices[0].message.content.strip()
        data = json.loads(content)

        # Extract quiz array from whatever structure is returned
        if isinstance(data, dict):
            if "quiz" in data:
                questions = data["quiz"]
            else:
                # fallback: grab first list value
                questions = next((v for v in data.values() if isinstance(v, list)), [])
        elif isinstance(data, list):
            questions = data
        else:
            return []

        # Validate each question has required fields and answer matches an option
        valid = []
        for q in questions:
            if not isinstance(q, dict):
                continue
            if not all(k in q for k in ("question", "options", "answer")):
                continue
            if not isinstance(q["options"], list) or len(q["options"]) != 4:
                continue
            # Fix answer if it doesn't exactly match any option (case-insensitive fix)
            if q["answer"] not in q["options"]:
                match = next((o for o in q["options"] if o.strip().lower() == q["answer"].strip().lower()), None)
                if match:
                    q["answer"] = match
                else:
                    continue  # skip broken questions
            valid.append(q)

        return valid[:10]

    except json.JSONDecodeError as e:
        print(f"!!! QUIZ JSON ERROR: {e}")
        return []
    except Exception as e:
        print(f"!!! QUIZ ERROR: {e}")
        return []