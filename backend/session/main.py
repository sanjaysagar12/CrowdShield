import sqlite3
import uuid
import os
import shutil
from typing import List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
import requests
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Crowd Shield API")

# Allow all origins (use with caution in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount video directory to serve static files
app.mount("/videos", StaticFiles(directory="uploaded_videos"), name="videos")

# Configuration
UPLOAD_DIR = "uploaded_videos"
DB_NAME = "crowd_shield.db"
MESSENGER_API_URL = "http://localhost:8003/send-message"
NOTIFY_PHONE_NUMBERS = os.getenv("NOTIFY_PHONE_NUMBERS", "").split(",")

# Ensure upload directory exists
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Database Setup
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            video_path TEXT NOT NULL,
            description TEXT,
            notify_to TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Check if new columns exist, if not add them (Migration)
    # This is a simple migration strategy for this dev environment
    try:
        cursor.execute("ALTER TABLE sessions ADD COLUMN camera_id TEXT")
    except sqlite3.OperationalError:
        pass # Column likely exists
        
    try:
        cursor.execute("ALTER TABLE sessions ADD COLUMN latitude TEXT")
    except sqlite3.OperationalError:
        pass
        
    try:
        cursor.execute("ALTER TABLE sessions ADD COLUMN longitude TEXT")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()

init_db()

# Pydantic models
class SessionResponse(BaseModel):
    session_id: str
    notify_to: str
    status: str
    description: str

    live_url: str
    video_url: str
    camera_id: str
    latitude: str
    longitude: str

class StatusUpdate(BaseModel):
    status: str  # 'approved' or 'rejected'

@app.post("/upload", response_model=List[SessionResponse])
async def upload_video(
    file: UploadFile = File(...),
    description: str = Form(...),
    notify_to: str = Form(...),  # Comma-separated list of recipients
    camera_id: str = Form("cam1"),
    latitude: str = Form("0.0"),
    longitude: str = Form("0.0")
):
    """
    Upload a video and create a session for each recipient in the notify_to list.
    notify_to should be a comma-separated string (e.g., "admin,security,user1").
    """
    try:
        # Save the video file
        file_extension = os.path.splitext(file.filename)[1]
        video_filename = f"{uuid.uuid4()}{file_extension}"
        video_path = os.path.join(UPLOAD_DIR, video_filename)
        
        with open(video_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Parse recipients
        recipients = [r.strip() for r in notify_to.split(",") if r.strip()]
        
        created_sessions = []
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        for recipient in recipients:
            session_id = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO sessions (session_id, video_path, description, notify_to, status, camera_id, latitude, longitude) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (session_id, video_path, description, recipient, "pending", camera_id, latitude, longitude)
            )
            created_sessions.append({
                "session_id": session_id,
                "notify_to": recipient,
                "status": "pending",
                "description": description,
                "description": description,
                "live_url": f"http://localhost:8000/video_feed/{camera_id}",
                "video_url": f"http://localhost:8002/videos/{video_filename}",
                "camera_id": camera_id,
                "latitude": latitude,
                "longitude": longitude
            })
            
        conn.commit()
        conn.close()
        
        # Send WhatsApp notifications
        for phone in NOTIFY_PHONE_NUMBERS:
            phone = phone.strip()
            if phone:
                try:
                    session_url = f"http://localhost:3000/session/{created_sessions[0]['session_id']}"
                    # Use the specific description provided by the agent (e.g., "Security Alert: Fire detected!")
                    desc = created_sessions[0]['description']
                    message_text = f"🚨 {desc}\n{session_url}"
                    requests.post(MESSENGER_API_URL, json={
                        "phone_no": phone,
                        "message": message_text
                    })
                    print(f"Notification sent to {phone}")
                except Exception as e:
                    print(f"Failed to send notification to {phone}: {e}")
        
        return created_sessions

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/session/{session_id}/approve")
async def approve_session(session_id: str):
    """Approve a specific session."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT session_id FROM sessions WHERE session_id = ?", (session_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")
        
    cursor.execute("UPDATE sessions SET status = 'approved' WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()
    return {"session_id": session_id, "status": "approved"}

@app.post("/session/{session_id}/reject")
async def reject_session(session_id: str):
    """Reject a specific session."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT session_id FROM sessions WHERE session_id = ?", (session_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")
        
    cursor.execute("UPDATE sessions SET status = 'rejected' WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()
    return {"session_id": session_id, "status": "rejected"}

@app.get("/session/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """Get details of a specific session."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT session_id, notify_to, status, description, video_path, camera_id, latitude, longitude FROM sessions WHERE session_id = ?", (session_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    
    response = dict(row)
    # Ensure backward compatibility if columns were NULL
    cam_id = response.get('camera_id') or "cam1"
    response['live_url'] = f"http://localhost:8000/video_feed/{cam_id}"
    response['camera_id'] = cam_id
    response['latitude'] = response.get('latitude') or "0.0"
    response['longitude'] = response.get('longitude') or "0.0"
    
    if response.get('video_path'):
         filename = os.path.basename(response['video_path'])
         response['video_url'] = f"http://localhost:8002/videos/{filename}"
    else:
         response['video_url'] = ""

    return response

@app.get("/sessions", response_model=List[SessionResponse])
async def list_sessions():
    """List all sessions."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT session_id, notify_to, status, description, video_path, camera_id, latitude, longitude FROM sessions")
    rows = cursor.fetchall()
    conn.close()
    
    results = []
    for row in rows:
        d = dict(row)
        cam_id = d.get('camera_id') or "cam1"
        d['live_url'] = f"http://localhost:8000/video_feed/{cam_id}"
        pass # video_url logic follows
        if d.get('video_path'):
            filename = os.path.basename(d['video_path'])
            d['video_url'] = f"http://localhost:8002/videos/{filename}"
        else:
             d['video_url'] = ""
        results.append(d)

    return results

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
