import cv2
import uvicorn
from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import threading
import time
import asyncio
from typing import Dict
from fastapi import FastAPI, Request, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect
from websockets import connect

app = FastAPI(title="Live Stream Hub")

# Allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store the latest frame for each camera
# Format: {camera_id: b'jpeg_bytes'}
streams: Dict[str, bytes] = {}
# Lock for thread safety when accessing streams
stream_lock = threading.Lock()

@app.websocket("/ws/push/{camera_id}")
async def websocket_endpoint(websocket: WebSocket, camera_id: str):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_bytes()
            with stream_lock:
                streams[camera_id] = data
    except WebSocketDisconnect:
        print(f"Camera {camera_id} disconnected")
    except Exception as e:
        print(f"Error in websocket {camera_id}: {e}")
    finally:
        with stream_lock:
            if camera_id in streams:
                del streams[camera_id]

@app.get("/active_cameras")
async def get_active_cameras():
    """Returns a list of currently active camera IDs."""
    with stream_lock:
        return {"cameras": list(streams.keys())}

    """
    Receive a frame from a vision model and update the stream.
    """
    try:
        contents = await file.read()
        with stream_lock:
            streams[camera_id] = contents
        return {"status": "ok", "camera_id": camera_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def generate_frames(camera_id: str):
    """
    Generator that yields frames for a specific camera.
    """
    while True:
        with stream_lock:
            frame_data = streams.get(camera_id)
        
        if frame_data:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_data + b'\r\n')
        else:
            # Check if we have any frame at all, if not, maybe yield a placeholder or wait
            # For now, just wait a bit to avoid busy loop if no stream
            pass
            
        time.sleep(0.033) # Approx 30 FPS

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
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Live Stream Hub</h1>
                <p>Access streams at <code>/video_feed/{camera_id}</code></p>
                
                <div class="camera-box">
                    <h3>Camera 1 (cam1)</h3>
                    <img src="/video_feed/cam1" alt="Waiting for stream..." />
                </div>
            </div>
        </body>
    </html>
    """

@app.get("/video_feed/{camera_id}")
async def video_feed(camera_id: str):
    return StreamingResponse(generate_frames(camera_id), media_type="multipart/x-mixed-replace; boundary=frame")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
