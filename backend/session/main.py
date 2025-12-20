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

# Configuration
UPLOAD_DIR = "uploaded_videos"
DB_NAME = "crowd_shield.db"
MESSENGER_API_URL = "http://localhost:8003/send-message"
NOTIFY_PHONE_NUMBERS = os.getenv("NOTIFY_PHONE_NUMBERS", "").split(",")

# Ensure upload directory exists
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Mount video directory to serve static files
app.mount("/videos", StaticFiles(directory="uploaded_videos"), name="videos")

# Database Setup
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # DROP existing table to reset schema (Requested by user)
    cursor.execute("DROP TABLE IF EXISTS sessions")
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            video_path TEXT NOT NULL,
            description TEXT,
            notify_to TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            camera_id TEXT,
            latitude TEXT,
            longitude TEXT,
            severity TEXT,
            confidence TEXT
        )
    ''')
    
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
    severity: str
    confidence: str

class StatusUpdate(BaseModel):
    status: str  # 'approved' or 'rejected'

@app.post("/upload", response_model=List[SessionResponse])
async def upload_video(
    file: UploadFile = File(...),
    description: str = Form(...),
    notify_to: str = Form(...),  # Comma-separated list of recipients
    camera_id: str = Form("cam1"),
    latitude: str = Form("0.0"),
    longitude: str = Form("0.0"),
    severity: str = Form("Normal"),
    confidence: str = Form("Unknown")
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
        # return dicts
        conn.row_factory = sqlite3.Row 
        cursor = conn.cursor()
        
        # Check for active session for this camera within last 30 minutes
        cursor.execute(
            "SELECT * FROM sessions WHERE camera_id = ? AND created_at >= datetime('now', '-30 minutes') ORDER BY created_at DESC LIMIT 1",
            (camera_id,)
        )
        active_session = cursor.fetchone()
        
        if active_session:
            # Update existing session
            session_id = active_session['session_id']
            print(f"Updating active session {session_id} for camera {camera_id}")
            
            cursor.execute(
                "UPDATE sessions SET video_path = ?, description = ?, severity = ?, confidence = ? WHERE session_id = ?",
                (video_path, description, severity, confidence, session_id)
            )
            
            # Fetch updated session details to return
            # We construct the response object based on the updated info and existing session data
            session_data = dict(active_session)
            session_data['video_path'] = video_path
            session_data['description'] = description
            session_data['severity'] = severity
            session_data['confidence'] = confidence
            
            # Helper to format response
            def format_response(row_dict):
                cam_id = row_dict.get('camera_id') or "cam1"
                vid_path = row_dict.get('video_path')
                vid_filename = os.path.basename(vid_path) if vid_path else ""
                
                return {
                    "session_id": row_dict['session_id'],
                    "notify_to": row_dict['notify_to'],
                    "status": row_dict['status'],
                    "description": row_dict['description'],
                    "live_url": f"http://localhost:8000/video_feed/{cam_id}",
                    "video_url": f"http://localhost:8002/videos/{vid_filename}" if vid_filename else "",
                    "camera_id": cam_id,
                    "latitude": row_dict.get('latitude') or "0.0",
                    "longitude": row_dict.get('longitude') or "0.0",
                    "severity": row_dict.get('severity') or "Normal",
                    "confidence": row_dict.get('confidence') or "Unknown"
                }

            created_sessions.append(format_response(session_data))
            
            # Commit changes
            conn.commit()
            conn.close()
            
            # SKIP Notification for updates
            print(f"Skipping notification for updated session {session_id}")
            
        else:
            # Create NEW session
            for recipient in recipients:
                session_id = str(uuid.uuid4())
                cursor.execute(
                    "INSERT INTO sessions (session_id, video_path, description, notify_to, status, camera_id, latitude, longitude, severity, confidence) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (session_id, video_path, description, recipient, "pending", camera_id, latitude, longitude, severity, confidence)
                )
                created_sessions.append({
                    "session_id": session_id,
                    "notify_to": recipient,
                    "status": "pending",
                    "description": description,
                    "live_url": f"http://localhost:8000/video_feed/{camera_id}",
                    "video_url": f"http://localhost:8002/videos/{video_filename}",
                    "camera_id": camera_id,
                    "latitude": latitude,
                    "longitude": longitude,
                    "severity": severity,
                    "confidence": confidence
                })
                
            conn.commit()
            conn.close()
            
            # Send WhatsApp notifications (ONLY for new sessions)
            for phone in NOTIFY_PHONE_NUMBERS:
                phone = phone.strip()
                if phone:
                    try:
                        session_url = f"http://localhost:3000/session/{created_sessions[0]['session_id']}"
                        desc = created_sessions[0]['description']
                        message_text = f"🚨 {desc}\nSeverity: {severity}\nConfidence: {confidence}\n{session_url}"
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
    
    cursor.execute("SELECT session_id, notify_to, status, description, video_path, camera_id, latitude, longitude, severity, confidence FROM sessions WHERE session_id = ?", (session_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    cam_id = row['camera_id'] or "cam1"
    vid_path = row['video_path']
    vid_filename = os.path.basename(vid_path) if vid_path else ""
    
    return {
        "session_id": row['session_id'],
        "notify_to": row['notify_to'],
        "status": row['status'],
        "description": row['description'],
        "live_url": f"http://localhost:8000/video_feed/{cam_id}",
        "video_url": f"http://localhost:8002/videos/{vid_filename}" if vid_filename else "",
        "camera_id": cam_id,
        "latitude": row['latitude'] or "0.0",
        "longitude": row['longitude'] or "0.0",
        "severity": row['severity'] or "Normal",
        "confidence": row['confidence'] or "Unknown"
    }

@app.get("/sessions", response_model=List[SessionResponse])
async def list_sessions():
    """List all sessions."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT session_id, notify_to, status, description, video_path, camera_id, latitude, longitude, severity, confidence FROM sessions")
    rows = cursor.fetchall()
    conn.close()
    
    results = []
    for row in rows:
        d = dict(row)
        cam_id = d.get('camera_id') or "cam1"
        d['live_url'] = f"http://localhost:8000/video_feed/{cam_id}"
        d['camera_id'] = cam_id
        d['latitude'] = d.get('latitude') or "0.0"
        d['longitude'] = d.get('longitude') or "0.0"
        d['severity'] = d.get('severity') or "Normal"
        d['confidence'] = d.get('confidence') or "Unknown"
        
        if d.get('video_path'):
            filename = os.path.basename(d['video_path'])
            d['video_url'] = f"http://localhost:8002/videos/{filename}"
        else:
             d['video_url'] = ""
        results.append(d)

    return results

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
