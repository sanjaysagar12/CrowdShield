from fastapi import FastAPI, UploadFile, File, HTTPException
import uvicorn
import shutil
from pathlib import Path
import os
import cv2
import google.generativeai as genai
from dotenv import load_dotenv
from PIL import Image
import io
import requests

load_dotenv()

# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("Warning: GEMINI_API_KEY not found in environment variables.")

genai.configure(api_key=GEMINI_API_KEY)

app = FastAPI(title="Agent API")

UPLOAD_DIR = Path("received_videos")
UPLOAD_DIR.mkdir(exist_ok=True)

def process_video_with_gemini(video_path: Path):
    """
    Extracts a frame from the video and asks Gemini if a person is present.
    """
    print(f"Processing video: {video_path}")
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print("Error opening video file")
        return False

    # Get total frames and pick a middle frame to ensure we see the scene
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    middle_frame_index = max(0, total_frames // 2)
    cap.set(cv2.CAP_PROP_POS_FRAMES, middle_frame_index)
    
    ret, frame = cap.read()
    cap.release()
    
    if not ret:
        print("Error reading frame from video")
        return False

    # Convert BGR (OpenCV) to RGB (PIL)
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    pil_image = Image.fromarray(rgb_frame)

    try:
        print("Sending frame to Gemini...")
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content([
            "Is there a person in this image? Answer with just YES or NO.",
            pil_image
        ])
        
        content = response.text.strip().upper()
        print(f"Gemini response: {content}")
        
        # Check if YES is in the response
        return "YES" in content
    except Exception as e:
        print(f"Gemini error: {e}")
        return False

def handle_person_not_present(video_path: Path):
    """
    Sends the video to the Crowd Shield API to create a session.
    """
    print("Person not present. Sending to Crowd Shield API...")
    crowd_shield_url = "http://localhost:8002/upload"
    
    try:
        with open(video_path, 'rb') as f:
            files = {'file': (video_path.name, f, 'video/mp4')}
            data = {
                'description': 'Security Alert: No person detected in monitored area.',
                'notify_to': 'admin,security'
            }
            response = requests.post(crowd_shield_url, files=files, data=data)
            
            if response.status_code == 200:
                print(f"Successfully created session: {response.json()}")
            else:
                print(f"Failed to create session. Status: {response.status_code}, Response: {response.text}")
                
    except Exception as e:
        print(f"Error sending to Crowd Shield API: {e}")

@app.post("/agent")
async def agent_endpoint(file: UploadFile = File(...)):
    try:
        file_path = UPLOAD_DIR / file.filename
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        print(f"Received video: {file.filename}")
        
        # Analyze video with Gemini
        is_person_present = process_video_with_gemini(file_path)
        
        if not is_person_present:
            handle_person_not_present(file_path)
        else:
            print("Person detected by Gemini.")
        
        return {
            "filename": file.filename, 
            "status": "processed", 
            "person_detected": is_person_present
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def root():
    return {"status": "Agent is running"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
