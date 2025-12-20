from fastapi import FastAPI, UploadFile, File, HTTPException, Form
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
        print("Sending frame to Gemini for validation...")
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content([
            "Analyze this image for safety. Classify it as one of the following:\n0 - Fire\n1 - Violence\n2 - Normal/Safe\nAlso provide a Severity (Critical/Warning/Informational) and a Confidence score (0-100%).\nReturn the response in this format:\nClass: [0/1/2]\nSeverity: [Severity]\nConfidence: [Score%]",
            pil_image
        ])
        
        content = response.text.strip()
        print(f"Gemini response: {content}")
        
        # Parse response
        event_type = "Normal"
        severity = "Normal"
        confidence = "0%"
        
        lines = content.split('\n')
        for line in lines:
            if "Class:" in line:
                if "0" in line: event_type = "Fire"
                elif "1" in line: event_type = "Violence"
                else: event_type = "Normal"
            if "Severity:" in line:
                severity = line.split("Severity:")[1].strip()
            if "Confidence:" in line:
                confidence = line.split("Confidence:")[1].strip()
        
        return {
            "event_type": event_type,
            "severity": severity,
            "confidence": confidence
        }

    except Exception as e:
        print(f"Gemini error: {e}")
        print("WARNING: Using dummy data for session due to API error.")
        # Fallback to dummy data as requested
        return {
            "event_type": "Violence",
            "severity": "Critical",
            "confidence": "Simulated (API Limit)"
        }

def handle_event(video_path: Path, event_data: dict, camera_id: str, latitude: str, longitude: str):
    """
    Sends the video to the Crowd Shield API to create a session for the event.
    """
    event_type = event_data['event_type']
    severity = event_data['severity']
    confidence = event_data['confidence']
    
    print(f"{event_type} detected. Sending to Crowd Shield API...")
    crowd_shield_url = "http://localhost:8002/upload"
    
    description = f"Security Alert: {event_type} detected!"
    
    try:
        with open(video_path, 'rb') as f:
            files = {'file': (video_path.name, f, 'video/mp4')}
            data = {
                'description': description,
                'notify_to': 'admin,security',
                'camera_id': camera_id,
                'latitude': latitude,
                'longitude': longitude,
                'severity': severity,
                'confidence': confidence
            }
            response = requests.post(crowd_shield_url, files=files, data=data)
            
            if response.status_code == 200:
                print(f"Successfully created session: {response.json()}")
            else:
                print(f"Failed to create session. Status: {response.status_code}, Response: {response.text}")
                
    except Exception as e:
        print(f"Error sending to Crowd Shield API: {e}")

@app.post("/agent")
async def agent_endpoint(
    file: UploadFile = File(...),
    camera_id: str = Form("cam1"),
    latitude: str = Form("0.0"),
    longitude: str = Form("0.0")
):
    try:
        file_path = UPLOAD_DIR / file.filename
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        print(f"Received video: {file.filename} from {camera_id} at {latitude},{longitude}")
        
        # Analyze video with Gemini
        result = process_video_with_gemini(file_path)
        event_result = result['event_type']
        
        if event_result == "Fire" or event_result == "Violence":
            handle_event(file_path, result, camera_id, latitude, longitude)
        else:
            print(f"Event judged as {event_result} (Safe/Normal). No action taken.")
        
        return {
            "filename": file.filename, 
            "status": "processed", 
            "event_detected": event_result,
            "details": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def root():
    return {"status": "Agent is running"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
