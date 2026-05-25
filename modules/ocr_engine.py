import easyocr
import os
from concurrent.futures import ThreadPoolExecutor

reader = easyocr.Reader(['en'], gpu=False)

def process_image(image_path):
    try:
        result = reader.readtext(image_path, detail=0)
        return " ".join(result)
    except:
        return ""

def extract_text_from_frames(folder="static/frames"):
    images = sorted(os.listdir(folder))[:30]
    image_paths = [os.path.join(folder, img) for img in images]
    max_workers = os.cpu_count() or 4

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(process_image, image_paths))

    return "\n".join(results)