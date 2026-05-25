from modules.youtube_downloader import download_youtube_video
from modules.frame_extractor import extract_frames
from modules.ocr_engine import extract_text_from_frames
from modules.summarizer import generate_structured_notes
from modules.translator import translate_notes
from modules.assignment_generator import generate_assignment
from modules.subtitle_extractor import get_subtitles
from modules.yt_transcript import get_transcript
import os

# Create output folder
os.makedirs("static/output", exist_ok=True)

url = input("Enter YouTube URL: ")

text = None

# 1️⃣ Try transcript (FASTEST)
try:
    text = get_transcript(url)
    print("✅ Using Transcript (fast)")
except:
    print("❌ Transcript not available")

# 2️⃣ Try subtitles
if not text:
    text = get_subtitles(url)
    if text:
        print("✅ Using Subtitles")
    else:
        print("❌ Subtitles not available")

# 3️⃣ Fallback OCR (SLOW)
if not text:
    print("⚠ Using OCR (slow)")
    video = download_youtube_video(url)

    if video:
        extract_frames(video)
        text = extract_text_from_frames()
    else:
        print("❌ Video download failed")
        exit()

# Show extracted text preview
print("\n📄 Extracted Text Preview:\n")
print(text[:500])

# ✨ Generate Notes (ONLY ONCE)
notes = generate_structured_notes(text[:4000])

print("\n📘 Structured Notes:\n")
print(notes)

# Save notes
with open("static/output/notes.txt", "w", encoding="utf-8") as f:
    f.write(notes)

# 🌍 Translate Notes
translated_notes = translate_notes(notes, "hi")

print("\n🌐 Translated Notes:\n")
print(translated_notes)

with open("static/output/translated_notes.txt", "w", encoding="utf-8") as f:
    f.write(translated_notes)

# 📝 Generate Assignment
assignment = generate_assignment(notes)

print("\n📝 Assignment:\n")
print(assignment)

with open("static/output/assignment.txt", "w", encoding="utf-8") as f:
    f.write(assignment)