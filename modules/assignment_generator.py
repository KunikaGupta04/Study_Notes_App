import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def generate_assignment(notes):
    prompt = f"""
    Based on these study notes, generate a study assignment.
    Format the output as a JSON object with three keys: "mcqs", "short_questions", and "long_questions".
    Each item must have a "question" and an "answer".
    
    Notes:
    {notes}
    
    Return ONLY the JSON.
    """

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )

    return json.loads(response.choices[0].message.content)