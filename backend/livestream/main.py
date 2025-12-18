import cv2
import uvicorn
from fastapi import FastAPI
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import threading

app = FastAPI(title="Live Stream API")

# Allow all origins (for iframe embedding on other sites)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Global variable to control camera access
camera = None

def get_camera():
    global camera
    if camera is None:
        camera = cv2.VideoCapture(0)
    return camera

def generate_frames():
    cam = get_camera()
    while True:
        success, frame = cam.read()
        if not success:
            break
        else:
            # Encode the frame in JPEG format
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            
            # Yield the frame in byte format
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <html>
        <head>
            <title>Live Stream</title>
            <style>
                body { font-family: sans-serif; text-align: center; padding: 20px; }
                .container { max-width: 800px; margin: 0 auto; }
                img { max-width: 100%; border: 2px solid #333; }
                .embed-code { background: #f0f0f0; padding: 10px; margin-top: 20px; border-radius: 5px; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Live Camera Stream</h1>
                <img src="/video_feed" />
                
                <div class="embed-code">
                    <h3>Embed this stream:</h3>
                    <code>&lt;iframe src="YOUR_PUBLIC_URL/video_feed" width="640" height="480"&gt;&lt;/iframe&gt;</code>
                    <p><small>Replace YOUR_PUBLIC_URL with this server's IP address or domain.</small></p>
                </div>
            </div>
        </body>
    </html>
    """

@app.get("/video_feed")
async def video_feed():
    return StreamingResponse(generate_frames(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.on_event("shutdown")
def shutdown_event():
    global camera
    if camera is not None:
        camera.release()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
