import cv2
import uvicorn
import numpy as np
import json
from fastapi import FastAPI, Request, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import threading
import time
import asyncio
from typing import Dict, Any
import os

app = FastAPI(title="Live Stream Hub")

# Allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store the latest frame and metadata for each camera
# Format: {camera_id: {'image': bytes, 'metadata': dict}}
streams: Dict[str, Dict[str, Any]] = {}

# Lock for thread safety
stream_lock = threading.Lock()

@app.websocket("/ws/push/{camera_id}")
async def websocket_endpoint(websocket: WebSocket, camera_id: str):
    await websocket.accept()
    try:
        while True:
            # Handle both text (metadata) and bytes (frame)
            # We use recieve() to get a Message object that has .type
            message = await websocket.receive()
            
            with stream_lock:
                if camera_id not in streams:
                    streams[camera_id] = {'image': None, 'metadata': {}}
                
                if message["type"] == "websocket.receive":
                    if "bytes" in message and message["bytes"] is not None:
                        streams[camera_id]['image'] = message["bytes"]
                    elif "text" in message and message["text"] is not None:
                         try:
                             meta = json.loads(message["text"])
                             if meta.get("type") == "detections":
                                 streams[camera_id]['metadata'] = meta
                         except json.JSONDecodeError:
                             pass
    except WebSocketDisconnect:
        print(f"Camera {camera_id} disconnected")
    except Exception as e:
        print(f"Error in websocket {camera_id}: {e}")
    finally:
        with stream_lock:
            # Maybe keep last frame for a bit? Or delete immediately?
            # Deleting for now to avoid stale streams
            if camera_id in streams:
                del streams[camera_id]

@app.get("/active_cameras")
async def get_active_cameras():
    """Returns a list of currently active camera IDs."""
    with stream_lock:
        return {"cameras": list(streams.keys())}
    
def process_frame(jpeg_bytes, metadata, mode):
    """Draws bounding boxes on frame based on mode."""
    if not jpeg_bytes:
        return None

    # Decode
    nparr = np.frombuffer(jpeg_bytes, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    if frame is None:
        return None

    # Draw based on mode
    if mode == "fight":
        detections = metadata.get("fight", [])
        color = (0, 0, 255) # Red
        label_prefix = "Fight"
    elif mode == "fire":
        detections = metadata.get("fire", [])
        color = (0, 165, 255) # Orange
        label_prefix = "Fire"
    else:
        detections = []
        color = (0, 255, 0)
        label_prefix = "Unknown"

    # Common Drawing Logic
    for d in detections:
        bbox = d.get('bbox')
        conf = d.get('confidence', 0.0)
        if bbox:
            x1, y1, x2, y2 = map(int, bbox)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, f"{label_prefix} {conf:.2f}", (x1, y1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
    
    # Re-encode
    ret, buffer = cv2.imencode('.jpg', frame)
    if ret:
        return buffer.tobytes()
    return None

def generate_frames(camera_id: str, mode: str = "fight"):
    """
    Generator that yields frames for a specific camera with requested visualization.
    """
    while True:
        frame_data = None
        metadata = {}
        
        with stream_lock:
            data = streams.get(camera_id)
            if data:
                frame_data = data.get('image')
                metadata = data.get('metadata', {})
        
        if frame_data:
            processed_frame = process_frame(frame_data, metadata, mode)
            if processed_frame:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + processed_frame + b'\r\n')
        
        time.sleep(0.033) # 30 FPS

@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <html>
        <head>
            <title>Live Stream Hub</title>
            <style>
                body { font-family: sans-serif; text-align: center; padding: 20px; }
                .container { max-width: 800px; margin: 0 auto; }
                .camera-box { margin-bottom: 30px; border: 1px solid #ccc; padding: 10px; border-radius: 8px; }
                img { max-width: 100%; border: 2px solid #333; }
                .controls { margin-top: 10px; }
                button { padding: 8px 16px; margin: 0 5px; cursor: pointer; }
            </style>
            <script>
                function setMode(mode) {
                    document.getElementById('stream_img').src = "/video_feed/cam1?mode=" + mode + "&t=" + new Date().getTime();
                }
            </script>
        </head>
        <body>
            <div class="container">
                <h1>Live Stream Hub</h1>
                <p>Toggle Visualization Mode:</p>
                <div class="controls">
                    <button onclick="setMode('fight')">Show Fight Detection</button>
                    <button onclick="setMode('fire')">Show Fire Detection</button>
                    <button onclick="setMode('none')">Raw Feed</button>
                </div>
                
                <div class="camera-box">
                    <h3>Camera 1 (cam1)</h3>
                    <img id="stream_img" src="/video_feed/cam1?mode=fight" alt="Waiting for stream..." />
                </div>
            </div>
        </body>
    </html>
    """

@app.get("/video_feed/{camera_id}")
async def video_feed(camera_id: str, mode: str = "fight"):
    return StreamingResponse(generate_frames(camera_id, mode), media_type="multipart/x-mixed-replace; boundary=frame")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
