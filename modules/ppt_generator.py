import re
import time
import requests

BASE_URL = "https://2slides.com/api/v1"


def parse_notes_to_slides(notes_raw):
    slides = []
    lines = notes_raw.split('\n')
    current_slide = None
    bullet_buffer = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith('## ') or line.startswith('### '):
            if current_slide and bullet_buffer:
                current_slide['content'] = bullet_buffer[:6]
                slides.append(current_slide)
                bullet_buffer = []
            prefix_len = 3 if line.startswith('## ') else 4
            current_slide = {'title': line[prefix_len:].strip(), 'content': []}
        elif line.startswith(('- ', '* ', '+ ')):
            clean = re.sub(r'\*\*(.*?)\*\*', r'\1', line[2:])
            bullet_buffer.append(clean[:120])
        elif current_slide and not line.startswith('#') and not line.startswith('```') and not line.startswith('|'):
            clean = re.sub(r'\*\*(.*?)\*\*', r'\1', line)
            if len(clean) > 20:
                bullet_buffer.append(clean[:120])

    if current_slide and bullet_buffer:
        current_slide['content'] = bullet_buffer[:6]
        slides.append(current_slide)

    return slides[:15]


def build_prompt(slides_data):
    lines = []
    for i, slide in enumerate(slides_data):
        lines.append(f"Slide {i + 1}: {slide['title']}")
        for bullet in slide['content']:
            lines.append(f"• {bullet}")
        lines.append("")
    return "\n".join(lines)


def get_free_theme_id(headers):
    queries = ["education", "professional", "minimal", "business", "clean"]
    for query in queries:
        try:
            resp = requests.get(
                f"{BASE_URL}/themes/search",
                headers=headers,
                params={"query": query, "limit": 5},
                timeout=15
            )
            if resp.status_code == 401:
                raise Exception("Invalid API key — 401 Unauthorized from 2Slides.")
            if resp.status_code == 200:
                data = resp.json()
                themes = data.get("data", {}).get("themes", [])
                if themes:
                    return themes[0]["id"]
        except Exception as e:
            raise Exception(f"Theme fetch failed: {str(e)}")
    return None


def poll_job(job_id, headers, timeout=120, interval=4):
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(
            f"{BASE_URL}/jobs/{job_id}",
            headers=headers,
            timeout=30
        )
        resp.raise_for_status()
        job = resp.json().get("data", resp.json())
        status = job.get("status", "")

        if status == "success":
            return job
        elif status == "failed":
            raise Exception(f"2Slides job failed: {job.get('message', 'unknown reason')}")

        time.sleep(interval)

    raise Exception("PPT generation timed out after 120 seconds. Try again.")


def generate_ppt_from_notes(notes_raw, api_key):
    if not api_key or not api_key.strip():
        return {"error": "SLIDES_API_KEY is empty or missing. Check your .env file and restart Flask."}

    slides_data = parse_notes_to_slides(notes_raw)
    if not slides_data:
        return {"error": "Could not parse slides from notes. Ensure notes have ## headings."}

    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json"
    }

    # Step 1: Get a free theme ID
    try:
        theme_id = get_free_theme_id(headers)
    except Exception as e:
        return {"error": str(e)}

    if not theme_id:
        return {"error": "Could not fetch a theme from 2Slides. Check your API key and credits."}

    # Step 2: Submit generation job
    prompt = build_prompt(slides_data)
    payload = {
        "userInput": prompt,
        "themeId": theme_id,
        "mode": "async",
        "responseLanguage": "Auto",
    }

    try:
        resp = requests.post(
            f"{BASE_URL}/slides/generate",
            headers=headers,
            json=payload,
            timeout=60
        )
    except requests.exceptions.ConnectionError as e:
        return {"error": f"Cannot reach 2Slides API: {e}"}
    except requests.exceptions.Timeout:
        return {"error": "Request to 2Slides timed out. Try again."}

    if resp.status_code == 401:
        return {"error": "Invalid SLIDES_API_KEY — 401 Unauthorized. Key used: " + api_key.strip()[:12] + "..."}
    if resp.status_code == 402:
        return {"error": "Insufficient 2Slides credits. Top up at 2slides.com/api."}
    if resp.status_code != 200:
        return {"error": f"2Slides API error {resp.status_code}: {resp.text[:300]}"}

    result = resp.json()
    job_data = result.get("data", result)
    job_id = job_data.get("jobId") or job_data.get("job_id")

    # Handle sync response
    if not job_id:
        download_url = (job_data.get("downloadUrl")
                        or job_data.get("download_url")
                        or job_data.get("url"))
        if download_url:
            return {"url": download_url, "success": True}
        return {"error": f"No jobId or downloadUrl in response: {result}"}

    # Step 3: Poll for completion
    try:
        finished = poll_job(job_id, headers)
    except Exception as e:
        return {"error": str(e)}

    download_url = (finished.get("downloadUrl")
                    or finished.get("download_url")
                    or finished.get("url"))

    if not download_url:
        return {"error": f"Job finished but no download URL found: {finished}"}

    return {"url": download_url, "success": True}