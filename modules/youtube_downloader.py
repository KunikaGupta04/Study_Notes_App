import yt_dlp
import os

def download_youtube_video(url, output_path="static/videos"):
    os.makedirs(output_path, exist_ok=True)

    ydl_opts = {
        'outtmpl': f'{output_path}/%(title)s.%(ext)s',
        'format': 'mp4'
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_path = ydl.prepare_filename(info)
        print("✅ Video downloaded:", video_path)
        return video_path
    except Exception as e:
        print("❌ Download error:", e)
        return None