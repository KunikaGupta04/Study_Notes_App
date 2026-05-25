import re
import os
import yt_dlp


def get_transcript(video_id):
    """
    Fetch transcript for a YouTube video.

    Strategy (fastest → slowest):
      1. youtube-transcript-api  — direct HTTP, no browser emulation (~1–3s)
      2. yt-dlp VTT download     — fallback if API fails or video has no captions
    """

    # ─────────────────────────────────────────────
    #  FAST PATH — youtube-transcript-api
    # ─────────────────────────────────────────────
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        # Try English first (new API style)
        try:
            fetcher = YouTubeTranscriptApi()
            transcript_list = fetcher.fetch(video_id, languages=['en', 'en-US', 'en-GB', 'en-IN'])
            text = ' '.join([entry.text for entry in transcript_list])
        except Exception:
            try:
                # Old API style (v0.x)
                transcript_list = YouTubeTranscriptApi.get_transcript(
                    video_id, languages=['en', 'en-US', 'en-GB', 'en-IN']
                )
                text = ' '.join([entry['text'] for entry in transcript_list])
            except Exception:
                # Fallback — no language filter, accepts any available language
                fetcher = YouTubeTranscriptApi()
                transcript_list = fetcher.fetch(video_id)
                text = ' '.join([entry.text for entry in transcript_list])

        text = re.sub(r'\s+', ' ', text).strip()
        if len(text) > 100:
            print(f"[transcript] ⚡ Fast path succeeded ({len(text)} chars)")
            return text

    except Exception as e:
        print(f"[transcript] Fast path failed: {e}")
        print("[transcript] Falling back to yt-dlp…")
        
    # ─────────────────────────────────────────────
    #  SLOW PATH — yt-dlp VTT download
    # ─────────────────────────────────────────────
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        vtt_path = f"static/output/transcript_{video_id}.en.vtt"

        # Re-use cached VTT to skip re-downloading the same video
        if os.path.exists(vtt_path):
            print(f"[transcript] Using cached VTT for {video_id}")
            with open(vtt_path, "r", encoding="utf-8") as f:
                raw = f.read()
            return _parse_vtt(raw)

        # Get absolute path to cookies.txt
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cookies_path = os.path.join(base_dir, "cookies.txt")

        os.makedirs("static/output", exist_ok=True)

        ydl_opts = {
            'skip_download':      True,
            'writeautomaticsub':  True,
            'writesubtitles':     True,
            'subtitlesformat':    'vtt',
            'subtitleslangs':     ['en', 'en-US', 'en-GB'],
            'outtmpl':            f'static/output/transcript_{video_id}',
            'quiet':              False,
            'ignoreerrors':       True,
            'http_headers': {
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/120.0.0.0 Safari/537.36'
                )
            }
        }

        # Add cookies if available
        if os.path.exists(cookies_path):
            ydl_opts['cookiefile'] = cookies_path
            print(f"[transcript] Using cookies from: {cookies_path}")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if os.path.exists(vtt_path):
            with open(vtt_path, "r", encoding="utf-8") as f:
                raw = f.read()
            text = _parse_vtt(raw)
            print(f"[transcript] yt-dlp succeeded for {video_id} ({len(text)} chars)")
            return text

        print(f"[transcript] yt-dlp: no VTT file found for {video_id}")
        return None

    except Exception as e:
        print(f"[transcript] yt-dlp fallback failed for {video_id}: {e}")
        return None


def _parse_vtt(raw: str) -> str:
    """Clean a raw VTT string into plain text."""
    text = re.sub(r'\d{2}:\d{2}:\d{2}\.\d+\s*-->\s*[^\n]+\n', '', raw)
    text = re.sub(r'<[^>]+>', '', text)          # strip HTML/VTT tags
    text = re.sub(r'WEBVTT[^\n]*\n', '', text)   # strip header
    text = re.sub(r'^NOTE\s.*$', '', text, flags=re.MULTILINE)  # strip NOTE blocks
    text = re.sub(r'\n+', ' ', text)             # collapse newlines
    text = re.sub(r'\s+', ' ', text).strip()     # collapse spaces
    return text
