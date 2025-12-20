import cv2
import sys
import os
import time
import asyncio
import threading
import requests
import numpy as np
from collections import deque
from pathlib import Path
import websockets

# Add current directory to path just in case
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

try:
    from fight_detection.model import FightDetector
    from fire_detection.model import FireDetector
except ImportError as e:
    print(f"Import Error: {e}")
    print("Ensure you are running from 'model/vision-model/' or that the directories 'fight_detection' and 'fire_detection' are accessible.")
    sys.exit(1)

# Configuration
CAMERA_ID = "cam1"
LIVESTREAM_URL = "ws://localhost:8000/ws/push/cam1"
AGENT_URL = "http://localhost:8001/agent"
BUFFER_SECONDS = 5
FPS = 30
LATITUDE = "0.0"
LONGITUDE = "0.0"

class VisionSystem:
    def __init__(self):
        print("Initializing Vision System...")
        self.fight_detector = FightDetector()
        self.fire_detector = FireDetector()
        
        self.cap = cv2.VideoCapture(0) # Default camera
        if not self.cap.isOpened():
            print("Warning: Could not open default camera (0). Trying 1...")
            self.cap = cv2.VideoCapture(1)
            
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 640)
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 480)
        
        self.buffer_size = FPS * BUFFER_SECONDS
        self.frame_buffer = deque(maxlen=self.buffer_size)
        
        self.is_running = True
        self.last_event_time = 0
        self.cooldown_seconds = 10 
        
        # Create recordings directory
        self.rec_dir = Path("recordings")
        self.rec_dir.mkdir(exist_ok=True)

    def upload_event_worker(self, video_path, event_type):
        """Thread worker to upload video to agent."""
        try:
            print(f"Uploading {video_path} to Agent...")
            with open(video_path, 'rb') as f:
                files = {'file': (video_path.name, f, 'video/mp4')}
                data = {
                    'camera_id': CAMERA_ID,
                    'latitude': LATITUDE,
                    'longitude': LONGITUDE
                }
                # Timeout to prevent hanging
                requests.post(AGENT_URL, files=files, data=data, timeout=30)
            print(f"Successfully sent {event_type} event to Agent.")
        except Exception as e:
            print(f"Failed to upload event: {e}")

    def trigger_event(self, frame_buffer_snapshot, event_type: str):
        """Save video and trigger upload."""
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        filename = f"{event_type}_{timestamp}.mp4"
        filepath = self.rec_dir / filename
        
        print(f"!!! {event_type} DETECTED !!! Saving clip to {filepath}")
        
        # Save video
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(str(filepath), fourcc, FPS, (self.width, self.height))
        
        for frame in frame_buffer_snapshot:
            out.write(frame)
        out.release()
        
        # Start upload thread
        t = threading.Thread(target=self.upload_event_worker, args=(filepath, event_type))
        t.start()

    async def run(self):
        print(f"Connecting to Livestream: {LIVESTREAM_URL}")
        
        async for websocket in websockets.connect(LIVESTREAM_URL):
            print("Connected to Livestream WebSocket.")
            try:
                while self.is_running:
                    ret, frame = self.cap.read()
                    if not ret:
                        print("Failed to read frame.")
                        await asyncio.sleep(0.1)
                        continue
                        
                    self.frame_buffer.append(frame)
                    
                    # Run Detections
                    # NOTE: Running sequentially here for simplicity. 
                    # For higher FPS, could move to thread pool, but YOLO is fast on GPU, 
                    # slower on CPU. Use small weights.
                    
                    fight_detections = self.fight_detector.detect(frame, conf_threshold=0.5)
                    fire_detections = self.fire_detector.detect(frame, conf_threshold=0.5)
                    
                    event_type = None
                    annotated_frame = frame.copy()
                    
                    # Annotate and check for events
                    if fight_detections:
                        event_type = "Violence"
                        for d in fight_detections:
                            x1, y1, x2, y2 = map(int, d['bbox'])
                            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                            cv2.putText(annotated_frame, f"Fight {d['confidence']:.2f}", (x1, y1 - 10),
                                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                                       
                    if fire_detections:
                        # Prioritize Fire? Or just keep Violence if both? Let's say Fire.
                        event_type = "Fire" 
                        for d in fire_detections:
                            x1, y1, x2, y2 = map(int, d['bbox'])
                            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 165, 255), 2)
                            cv2.putText(annotated_frame, f"Fire {d['confidence']:.2f}", (x1, y1 - 10),
                                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 2)

                    # Trigger Event if Cooldown passed
                    if event_type:
                        current_time = time.time()
                        if current_time - self.last_event_time > self.cooldown_seconds:
                            self.last_event_time = current_time
                            # Pass a COPY of current buffer
                            self.trigger_event(list(self.frame_buffer), event_type)
                            
                        # Add Alert Text
                        cv2.putText(annotated_frame, f"ALERT: {event_type}", (50, 50),
                                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)

                    # Send to Livestream
                    try:
                        ret_enc, buffer = cv2.imencode('.jpg', annotated_frame)
                        if ret_enc:
                            await websocket.send(buffer.tobytes())
                    except Exception as e:
                        print(f"WS Send Error: {e}")
                        break # Break inner loop to reconnect

                    # Small sleep to yield to event loop
                    await asyncio.sleep(0.001)
            except websockets.exceptions.ConnectionClosed:
                print("WebSocket connection closed. Reconnecting...")
                await asyncio.sleep(3)
            except Exception as e:
                print(f"Error in run loop: {e}")
                await asyncio.sleep(3)

if __name__ == "__main__":
    system = VisionSystem()
    try:
        asyncio.run(system.run())
    except KeyboardInterrupt:
        print("Stopping...")
        system.cap.release()
