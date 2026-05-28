import os
import re
from flask import (Flask, render_template, request, jsonify, session, send_file, redirect, url_for)
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "smartnotes_secret_key_2024")

from flask_session import Session

app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = os.path.join(os.path.dirname(__file__), 'flask_session_data')  # ← set FIRST
app.config['SESSION_PERMANENT'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)  # ← then makedirs
Session(app)

def get_gemini_client():
    from google import genai
    from modules.gemini_client import VALID_KEYS
    import random
    key = random.choice(VALID_KEYS)
    return genai.Client(api_key=key)


def extract_video_id(url):
    regex = r"(?:v=|\/)([0-9A-Za-z_-]{11}).*"
    match = re.search(regex, url)
    return match.group(1) if match else None


@app.route('/')
def index():
    return render_template('index.html')

def is_video_educational(video_id, transcript_snippet):
    """The AI Gatekeeper logic"""
    from modules.gemini_client import get_client

    # Check 1: Expanded keyword list — covers Hindi/Urdu/regional content too
    forbidden_words = [
        'song', 'official video', 'lyrics', 'music video', 'audio',
        'full video', 'sad song', 'love song', 'romantic', 'lofi',
        'gaana', 'gana', 'filmi', 'bollywood', 'kollywood', 'tollywood',
        'lyrical video', 'feat.', 'ft.', 'album', 'single', 'track',
        'subscribe for more songs', 'like share','nursery rhyme', 'nursery rhymes', 
        'wheels on the bus', 'baby shark',
        'kids song', 'children song', 'rhyme', 'lullaby', 'cartoon',
        'cocomelon', 'bounce patrol', 'little baby bum', 'sing along',
        'for kids', 'for babies', 'for children', 'bedtime song',
        'bhajan', 'bhajans', 'aarti', 'kirtan', 'mantra', 'chalisa',
        'hanuman chalisa', 'durga', 'ganesh', 'shiva', 'krishna bhajan',
        'mata ki', 'jai mata', 'devotional', 'devotional song',
        'prayer song', 'religious song', 'pooja', 'stuti', 'stotra',
        'ambe tu hai', 'jai shri', 'om jai', 'ram bhajan','bhajan', 'bhajans', 'aarti', 'kirtan', 'mantra', 'chalisa',
        'hanuman chalisa', 'durga', 'ganesh', 'shiva', 'krishna bhajan',
        'mata ki', 'jai mata', 'devotional', 'devotional song',
        'prayer song', 'religious song', 'pooja', 'stuti', 'stotra',
        'ambe tu hai', 'jai shri', 'om jai', 'ram bhajan',
    ]
    if any(word in transcript_snippet.lower() for word in forbidden_words):
        return False, "SmartNotes only works with educational content like lectures, tutorials, and documentaries — not songs or entertainment videos."

    # Check 2: Stronger AI prompt with more context + explicit Hindi awareness
    client = get_client()
    prompt = f"""You are a strict content classifier for an educational notes app.

Your job: decide if this YouTube transcript is from EDUCATIONAL content or NOT.

EDUCATIONAL = lecture, tutorial, documentary, news report, explainer, how-to guide, course, interview about a topic.
NOT EDUCATIONAL = song, music video, nursery rhyme, kids rhyme, baby poem, movie scene,
film dialogue, entertainment show, sports commentary, prank, vlog, reaction video,
poem, chant, repetitive lyrics, children's content, bhajan, aarti, kirtan, mantra,
devotional song, religious chant, prayer, qawwali, gospel song, hymn, spiritual song,
any content that is primarily music or singing regardless of language or religion.

IMPORTANT: If the text looks like song lyrics or film dialogue (even in Hindi, Urdu, or any other language), classify it as NOT EDUCATIONAL.

Transcript sample:
\"\"\"
{transcript_snippet[:2000]}
\"\"\"

Reply with ONLY one word: VALID or INVALID."""

    try:
        response = client.models.generate_content(model="gemini-2.0-flash-lite", contents=prompt)
        decision = response.text.strip().upper()
        is_valid = "VALID" in decision and "INVALID" not in decision
        return is_valid, "SmartNotes only works with educational content like lectures, tutorials, and documentaries — not songs or entertainment videos."
    except:
        return True, ""
    
@app.route('/generate', methods=['POST'])
def generate():
    video_url = request.form.get('video_url', '').strip()
    video_id = extract_video_id(video_url)
    if not video_id:
        return jsonify({"error": "Invalid YouTube URL."}), 400

    try:
        from modules.yt_transcript import get_transcript
        transcript = get_transcript(video_id)
        
        if not transcript:
            return jsonify({"error": "No transcript found."}), 404

        # 🛑 ADDED GATEKEEPER CHECK HERE 🛑
        # We pass the first 1200 characters to the AI to decide if it's study material
        is_valid, error_msg = is_video_educational(video_id, transcript[:2000])
        
        if not is_valid:
            # This stops the process and returns the error to your frontend
            return jsonify({"success": False, "error": error_msg}), 400

        # If it passes the check, then we proceed to make notes
        from modules.summarizer import generate_structured_notes
        notes_html, notes_raw = generate_structured_notes(transcript)
        
        if notes_html.startswith("Error:"):
            return jsonify({"error": notes_html}), 503
            
        session['notes_html'] = notes_html
        session['notes_raw'] = notes_raw
        session['video_id'] = video_id
        session['video_url'] = video_url
        session.modified = True
        return jsonify({"success": True})

    except Exception as e:
        import traceback
        return jsonify({"error": traceback.format_exc()}), 500

@app.route('/notes')
def notes_page():
    if not session.get('notes_html'):
        return redirect(url_for('index'))
    # Pass notes directly into template — no separate API call needed
    return render_template('notes.html',
        notes_html=session.get('notes_html', ''),
        notes_raw=session.get('notes_raw', '')
    )


@app.route('/api/notes')
def api_notes():
    return jsonify({
        "notes": session.get('notes_html', ''),
        "notes_raw": session.get('notes_raw', '')
    })

@app.route('/debug/session')
def debug_session():
    return jsonify({
        "has_notes_raw": bool(session.get('notes_raw')),
        "notes_raw_len": len(session.get('notes_raw', '')),
        "has_notes_html": bool(session.get('notes_html')),
        "notes_html_len": len(session.get('notes_html', '')),
    })

@app.route('/translate', methods=['POST'])
def handle_translation():
    target_lang = request.form.get("language", "hindi")
    notes_raw = session.get('notes_raw', '')

    if not notes_raw:
        return jsonify({"error": "Session expired. Please go back and generate notes again."}), 400

    notes_trimmed = notes_raw[:12000]

    prompt = (
        f"Translate the following Markdown study notes to {target_lang}.\n\n"
        f"STRICT RULES:\n"
        f"1. Translate ONLY human-readable text.\n"
        f"2. Keep ALL Markdown syntax untouched: ##, ###, **, -, tables.\n"
        f"3. Keep ALL ```mermaid``` blocks EXACTLY as-is.\n"
        f"4. Output ONLY the translated Markdown. No explanation.\n\n"
        f"NOTES:\n{notes_trimmed}"
    )

    from google import genai
    from modules.gemini_client import VALID_KEYS, MODELS
    from modules.summarizer import convert_to_html
    import time

    last_error = "All API keys exhausted."

    for api_key in VALID_KEYS:
        client = genai.Client(api_key=api_key)
        for model in MODELS:
            try:
                response = client.models.generate_content(
                    model=model, contents=prompt
                )
                translated_raw = response.text.strip()
                if not translated_raw:
                    continue
                translated_html = convert_to_html(translated_raw)
                session['notes_html'] = translated_html
                session['notes_raw'] = translated_raw
                session.modified = True        # ← force session save
                return jsonify({"notes": translated_html, "success": True})
            except Exception as e:
                err = str(e)
                last_error = err
                if "429" in err or "503" in err:
                    time.sleep(2)
                    continue
                elif "404" in err:
                    break
                else:
                    time.sleep(1)
                    continue

    return jsonify({"error": f"Translation failed: {last_error}"}), 500

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_query = data.get("message", "").strip()
    notes_context = session.get('notes_raw', "")[:6000]

    prompt = f"""You are a smart study assistant for SmartNotes AI.

A student is studying a video and has these notes:
---
{notes_context}
---

STUDENT QUESTION: {user_query}

YOUR BEHAVIOR RULES:
1. If the question is DIRECTLY answered in the notes → answer from notes, mention it.
2. If the question is RELATED to the video's topic but needs extra explanation 
   (e.g. defining a term, explaining a concept briefly mentioned) → 
   answer helpfully using your knowledge, but connect it back to the notes context.
3. If the question is COMPLETELY UNRELATED to the video topic 
   (e.g. asking about cricket when notes are about Python) → 
   politely say: "That topic isn't covered in this video. 
   I'm best used for questions related to what you're currently studying."

TONE: Friendly, concise, student-focused. Use examples where helpful.
FORMAT: Use bullet points or short paragraphs. Keep it under 150 words unless 
the question genuinely needs more detail.

Never say "outside the scope" in a robotic way. Always be helpful first."""

    from modules.summarizer import VALID_KEYS, MODELS
    from google import genai
    import time

    for api_key in VALID_KEYS:
        client = genai.Client(api_key=api_key)
        for model in MODELS:
            try:
                response = client.models.generate_content(
                    model=model, contents=prompt
                )
                return jsonify({"response": response.text})
            except Exception as e:
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    time.sleep(2)
                    continue
                elif "404" in str(e):
                    break
                else:
                    continue

    return jsonify({"response": "All AI keys are at limit. Try again in a minute."}), 503

@app.route('/chat-screenshot', methods=['POST'])
def chat_screenshot():
    """Gemini Vision — explains a screenshot using notes as context."""

    if 'screenshot' not in request.files:
        return jsonify({'reply': 'No screenshot uploaded.'}), 400

    file = request.files['screenshot']
    if not file or file.filename == '':
        return jsonify({'reply': 'No file selected.'}), 400

    # Validate MIME type
    allowed_types = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}
    mime_type = file.content_type or 'image/jpeg'
    if mime_type not in allowed_types:
        return jsonify({'reply': 'Only JPG, PNG, or WEBP images are supported.'}), 400

    # Read & size-check (max 5 MB)
    image_bytes = file.read()
    if len(image_bytes) > 5 * 1024 * 1024:
        return jsonify({'reply': 'Image too large. Please use an image under 5 MB.'}), 400

    # Get optional follow-up question
    user_question  = request.form.get('question', '').strip()
    notes_context  = session.get('notes_raw', '')[:5000]

    if not notes_context:
        return jsonify({'reply': 'No notes found in session. Please generate notes first.'})

    # Build prompt
    question_part = f"\n\nStudent's specific question: {user_question}" if user_question else ""
    prompt = (
        "You are a helpful study assistant for SmartNotes AI.\n\n"
        "A student shared a screenshot taken from a YouTube educational video they are studying.\n\n"
        f"Here are the notes already generated from this video:\n---\n{notes_context}\n---\n\n"
        "Your task:\n"
        "1. Look carefully at the screenshot and identify what is shown "
        "(concept, diagram, equation, slide, code, graph, etc.)\n"
        "2. Explain it clearly in student-friendly language\n"
        "3. Connect it to the notes context where relevant\n"
        "4. If it shows a diagram or flowchart, explain each component\n"
        "5. If it shows an equation or formula, break it down step by step\n"
        "6. Keep the explanation concise, well-structured, and easy to understand\n"
        f"{question_part}\n\n"
        "Do NOT make up information that is not visible in the screenshot or present in the notes."
    )

    from google import genai
    from google.genai import types
    from modules.gemini_client import VALID_KEYS, MODELS
    import time

    for api_key in VALID_KEYS:
        client = genai.Client(api_key=api_key)
        for model in MODELS:
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=[
                        types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                        types.Part.from_text(text=prompt),
                    ]
                )
                return jsonify({'reply': response.text.strip()})
            except Exception as e:
                err = str(e)
                if any(c in err for c in ["429", "503", "quota", "UNAVAILABLE"]):
                    time.sleep(3)
                    continue
                elif "404" in err:
                    break
                else:
                    continue

    return jsonify({'reply': 'All API keys are at limit. Please try again in a minute.'}), 503


@app.route('/related-videos', methods=['GET'])
def related_videos():
    """Fetch related educational YouTube videos based on current notes topic."""

    video_id     = session.get('video_id', '')
    notes_raw    = session.get('notes_raw', '')
    if not notes_raw:
        return jsonify({'error': 'No notes found. Please generate notes first.'}), 400

    api_key = os.getenv('YOUTUBE_API_KEY', '').strip()
    if not api_key:
        return jsonify({'error': 'YouTube API key not configured.'}), 500

    # ── Step 1: Extract topic from notes using Gemini ──
    try:
        from modules.gemini_client import VALID_KEYS, MODELS
        from google import genai
        topic_query = None

        for key in VALID_KEYS:
            client = genai.Client(api_key=key)
            try:
                resp = client.models.generate_content(
                    model=MODELS[0],
                    contents=(
                        f"You are a YouTube search expert.\n\n"
                        f"Read these study notes carefully and identify the SPECIFIC topic being taught.\n"
                        f"Then write a YouTube search query (5-8 words) that would find similar "
                        f"educational tutorial videos on the SAME specific subject.\n\n"
                        f"Rules:\n"
                        f"- Be SPECIFIC (e.g. 'python list comprehension tutorial' not 'overview')\n"
                        f"- Include the subject name + key concept + 'tutorial' or 'explained'\n"
                        f"- NEVER return generic words like 'overview', 'introduction', 'summary'\n"
                        f"- Return ONLY the search query, no quotes, no explanation\n\n"
                        f"Notes:\n{notes_raw[:2000]}"
                    )
                )
                topic_query = resp.text.strip().strip('"').strip("'")
                # Reject if too generic
                generic = ['overview', 'introduction', 'summary', 'notes', 'educational tutorial']
                if any(topic_query.lower() == g for g in generic) or len(topic_query) < 8:
                    topic_query = None
                else:
                    break
            except Exception:
                continue

        if not topic_query:
            # Smarter fallback: find first non-generic heading
            generic_headings = ['overview','introduction','summary','core concepts',
                                 'how it works','key takeaways','applications','comparison']
            for match in re.finditer(r'##\s+(.+)', notes_raw):
                heading = match.group(1).strip()
                if not any(g in heading.lower() for g in generic_headings):
                    topic_query = heading + ' tutorial explained'
                    break
            if not topic_query:
                topic_query = "educational tutorial"

    except Exception as e:
        topic_query = "educational tutorial"

    # ── Step 2: Search YouTube Data API v3 ──
    try:
        import requests as _requests

        params = {
            'part':             'snippet',
            'q':                topic_query,
            'type':             'video',
            'maxResults':       8,
            'videoEmbeddable':  'true',
            'relevanceLanguage':'en',
            'safeSearch':       'strict',
            'key':              api_key,
        }
        resp = _requests.get(
            'https://www.googleapis.com/youtube/v3/search',
            params=params,
            timeout=10
        )

        if resp.status_code == 400:
            return jsonify({'error': 'Invalid YouTube API key or bad request.'}), 400
        if resp.status_code == 403:
            return jsonify({'error': 'YouTube API quota exceeded or key restricted.'}), 403
        if resp.status_code != 200:
            return jsonify({'error': f'YouTube API returned {resp.status_code}'}), 500

        data = resp.json()

        videos = []
        for item in data.get('items', []):
            vid_id  = item['id'].get('videoId', '')
            snippet = item.get('snippet', {})
            if not vid_id or vid_id == video_id:
                continue
            thumbs  = snippet.get('thumbnails', {})
            thumb   = (thumbs.get('high') or thumbs.get('medium') or thumbs.get('default') or {}).get('url', '')
            videos.append({
                'id':          vid_id,
                'title':       snippet.get('title', 'Untitled'),
                'channel':     snippet.get('channelTitle', ''),
                'thumbnail':   thumb,
                'url':         f'https://www.youtube.com/watch?v={vid_id}',
                'published':   snippet.get('publishedAt', '')[:10],
            })

        return jsonify({'videos': videos[:6], 'query': topic_query})

    except Exception as e:
        return jsonify({'error': f'YouTube API error: {str(e)}'}), 500


@app.route('/debug/gemini')
def debug_gemini():
    from google import genai
    from modules.gemini_client import VALID_KEYS, MODELS
    results = []
    for i, key in enumerate(VALID_KEYS):
        try:
            client = genai.Client(api_key=key)
            r = client.models.generate_content(
                model=MODELS[0],
                contents="Reply with just the word: OK"
            )
            results.append(f"Key {i+1}: ✅ {r.text.strip()}")
        except Exception as e:
            results.append(f"Key {i+1}: ❌ {str(e)[:120]}")
    return "<br>".join(results)

@app.route('/quiz')
def quiz_page():
    if not session.get('notes_raw'):
        return redirect(url_for('index'))
    return render_template('quiz.html')  # render immediately, load quiz via JS


@app.route('/api/quiz')
def api_quiz():
    notes_raw = session.get('notes_raw', '')
    if not notes_raw:
        return jsonify({"error": "No notes found. Please generate notes first."}), 400
    try:
        from modules.quiz_generator import generate_quiz
        quiz_data = generate_quiz(notes_raw)
        if not quiz_data:
            return jsonify({"error": "Quiz generation failed. Please try again."}), 500
        return jsonify({"quiz": quiz_data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500 

@app.route('/questions')
def questions_page():
    if not session.get('notes_raw'):
        return redirect(url_for('index'))
    from modules.assignment_generator import generate_assignment
    data = generate_assignment(session['notes_raw'])
    return render_template('questions.html', data=data)


@app.route('/export/pdf')
def export_pdf():
    notes_raw = session.get('notes_raw', '')
    if not notes_raw:
        return "No notes in session. Generate notes first, then export.", 400
    try:
        from modules.export_manager import generate_pdf
        pdf_stream = generate_pdf(notes_raw)
        return send_file(pdf_stream, download_name='smartnotes.pdf',
                         as_attachment=True, mimetype='application/pdf')
    except Exception as e:
        return f"PDF generation error: {str(e)}", 500


@app.route('/export/docx')          # ← fixed: added missing @
def export_docx():
    notes_raw = session.get('notes_raw', '') or session.get('notes', '')
    if not notes_raw:
        return "No notes in session. Generate notes first.", 400
    try:
        from modules.export_manager import generate_word
        doc_stream = generate_word(notes_raw)
        return send_file(
            doc_stream,
            download_name='smartnotes.docx',
            as_attachment=True,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
    except Exception as e:
        import traceback
        return f"<pre>Word error:\n{traceback.format_exc()}</pre>", 500


@app.route('/debug/word')
def debug_word():
    try:
        from modules.export_manager import generate_word
        stream = generate_word("# Title\n## Section\n- bullet one\n- bullet two\nSome paragraph.")
        return send_file(
            stream,
            download_name='test.docx',
            as_attachment=True,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
    except Exception as e:
        import traceback
        return f"<pre>{traceback.format_exc()}</pre>", 500


@app.route('/export/ppt', methods=['POST'])
def export_ppt():
    # Force re-read .env on every request so key changes take effect without restart
    load_dotenv(override=True)

    notes_raw = session.get('notes_raw', '')
    if not notes_raw:
        return jsonify({"error": "No notes in session. Generate notes first."}), 400

    api_key = os.getenv("SLIDES_API_KEY", "").strip()
    if not api_key:
        return jsonify({"error": "SLIDES_API_KEY missing from .env file"}), 500

    # Log the key prefix so you can confirm which key is actually loaded
    app.logger.info(f"PPT export using key: {api_key[:12]}...")

    try:
        from modules.ppt_generator import generate_ppt_from_notes
        result = generate_ppt_from_notes(notes_raw, api_key)
        if result.get("error"):
            return jsonify({"error": result["error"]}), 500
        return jsonify({"url": result["url"], "success": True})
    except Exception as e:
        return jsonify({"error": f"PPT error: {str(e)}"}), 500
    
@app.route('/load_from_history', methods=['POST'])
def load_from_history():
    from modules.summarizer import convert_to_html
    data = request.json
    raw = data.get('notes_raw', '')
    if not raw:
        return jsonify({"error": "No notes provided"}), 400
    session['notes_raw'] = raw
    session['notes_html'] = convert_to_html(raw)
    session.modified = True
    return jsonify({"success": True})

@app.route('/reset', methods=['POST'])
def reset_session():
    session.clear()
    return jsonify({"success": True})


@app.route('/history')
def history_page():
    return render_template('history.html')

if __name__ == '__main__':
    os.makedirs('data', exist_ok=True)
    os.makedirs('static/output', exist_ok=True)
    app.run(debug=True, port=5000)