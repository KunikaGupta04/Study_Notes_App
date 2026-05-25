def extract_frames(video_path, frame_rate=2):
    import cv2, os

    output_folder = "static/frames"
    os.makedirs(output_folder, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    fps = int(cap.get(cv2.CAP_PROP_FPS))

    count = 0
    frame_id = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if count % (fps * frame_rate) == 0:
            cv2.imwrite(f"{output_folder}/frame_{frame_id}.jpg", frame)
            frame_id += 1

        count += 1

    cap.release()