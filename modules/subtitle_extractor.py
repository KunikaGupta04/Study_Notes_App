import yt_dlp
import time
import os

def get_subtitles(url):
    file_path = "static/output/subtitles.en.vtt"

    if os.path.exists(file_path):
        os.remove(file_path)

    ydl_opts = {
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitlesformat': 'vtt',
        'outtmpl': 'static/output/subtitles',
        'http_headers': {'User-Agent': 'Mozilla/5.0'},
        'quiet': True
    }

    for attempt in range(3):
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    return f.read()
            return None

        except Exception as e:
            print(f"Attempt {attempt+1} failed: {e}")
            time.sleep(5)

    return None