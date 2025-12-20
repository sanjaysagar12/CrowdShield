import cv2
import time
import requests
import os
from pathlib import Path

# Config
CAMERA_INDEX = 1 # OBS Virtual Cam
DURATION = 20 # seconds
OUTPUT_DIR = "manual_recordings"
AGENT_URL = "http://localhost:8001/agent"
CAMERA_ID = "cam1_test"
LATITUDE = "12.9716"
LONGITUDE = "77.5946"

def main():
    Path(OUTPUT_DIR).mkdir(exist_ok=True)
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    filename = f"manual_test_{timestamp}.mp4"
    filepath = os.path.join(OUTPUT_DIR, filename)

    print(f"Opening Camera {CAMERA_INDEX}...")
    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        print(f"Failed to open camera {CAMERA_INDEX}, trying 0...")
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("Failed to open any camera.")
            return

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 640)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 480)
    fps = 15.0

    # Use mp4v since avc1 failed
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(filepath, fourcc, fps, (width, height))

    start_time = time.time()
    print(f"Recording {DURATION} seconds to {filepath}...")

    while (time.time() - start_time) < DURATION:
        ret, frame = cap.read()
        if not ret:
            print("Failed to read frame")
            break
        out.write(frame)
        
        # Display feedback
        elapsed = int(time.time() - start_time)
        cv2.putText(frame, f"REC {elapsed}/{DURATION}s", (50, 50), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        cv2.imshow("Recording Test", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    out.release()
    cv2.destroyAllWindows()
    print("Recording complete.")

    # Upload
    print(f"Uploading to Agent at {AGENT_URL}...")
    try:
        with open(filepath, 'rb') as f:
            files = {'file': (filename, f, 'video/mp4')}
            data = {
                'camera_id': CAMERA_ID,
                'latitude': LATITUDE,
                'longitude': LONGITUDE
            }
            response = requests.post(AGENT_URL, files=files, data=data)
            print("Upload Response Code:", response.status_code)
            print("Response:", response.text)
    except Exception as e:
        print(f"Upload failed: {e}")

if __name__ == "__main__":
    main()
