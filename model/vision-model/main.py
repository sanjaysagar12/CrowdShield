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
    from weapon_detection.model import WeaponDetector
except ImportError as e:
    print(f"Import Error: {e}")
    print("Ensure you are running from 'model/vision-model/' or that the directories 'fight_detection' and 'fire_detection' are accessible.")
    sys.exit(1)

# Configuration
CAMERA_ID = "cam1"
LIVESTREAM_URL = "ws://localhost:8000/ws/push/cam1"
AGENT_URL = "http://localhost:8001/agent"
BUFFER_SECONDS = 20
FPS = 15
LATITUDE = "0.0"
LONGITUDE = "0.0"
# Camera Index: 0 is usually the built-in webcam. 1 is often the OBS Virtual Camera if the webcam is present.
CAMERA_INDEX = 1 

class VisionSystem:
    def __init__(self):
        print("Initializing Vision System...")
        self.fight_detector = FightDetector()
        self.fire_detector = FireDetector()
        self.weapon_detector = WeaponDetector()
        
        print(f"Opening Camera Index: {CAMERA_INDEX} (Targeting OBS Virtual Camera)")
        self.cap = cv2.VideoCapture(CAMERA_INDEX)
        
        if not self.cap.isOpened():
            print(f"Warning: Could not open camera {CAMERA_INDEX}. Trying default 0...")
            self.cap = cv2.VideoCapture(0)
            
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 640)
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 480)
        
        self.buffer_size = FPS * BUFFER_SECONDS
        self.frame_buffer = deque(maxlen=self.buffer_size)
        
        self.is_running = True
        self.last_event_time = 0
        self.cooldown_seconds = 10 
        
        # Create recordings directory
        self.rec_dir = Path("recordings")
        self.latest_frame = None
        self.frame_lock = threading.Lock()
        
        # Start capture thread
        self.capture_thread = threading.Thread(target=self.capture_worker, daemon=True)
        self.capture_thread.start()

    def capture_worker(self):
        """Thread to capture frames at fixed FPS."""
        print("Capture thread started.")
        while self.is_running:
            if not self.cap.isOpened():
                time.sleep(1)
                continue
                
            ret, frame = self.cap.read()
            if ret:
                with self.frame_lock:
                    self.latest_frame = frame
                    self.frame_buffer.append(frame)
            else:
                print("Warning: Could not read frame in capture thread.")
                time.sleep(1)
            
            # Maintain approximate FPS
            time.sleep(1.0 / FPS)

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
        # Use avc1 (H.264) for better browser compatibility
        fourcc = cv2.VideoWriter_fourcc(*'avc1')
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
                    # Get latest frame from thread
                    frame = None
                    with self.frame_lock:
                        if self.latest_frame is not None:
                            frame = self.latest_frame.copy()
                            
                    if frame is None:
                        # No frame yet
                        await asyncio.sleep(0.1)
                        continue
                        
                    # Run Detections
                    # These run as fast as possible (likely slower than FPS)
                    fight_detections = self.fight_detector.detect(frame, conf_threshold=0.5)
                    fire_detections = self.fire_detector.detect(frame, conf_threshold=0.5)
                    weapon_detections = self.weapon_detector.detect(frame, conf_threshold=0.5)
                    
                    # Prepare Metadata
                    import json
                    metadata = {
                        "type": "detections",
                        "fight": fight_detections,
                        "fire": fire_detections,
                        "weapon": weapon_detections
                    }
                    
                    # Send Metadata (Text)
                    try:
                        await websocket.send(json.dumps(metadata))
                    except Exception as e:
                        print(f"WS Send JSON Error: {e}")
                        break

                    # Check for events to trigger recording (local logic)
                    event_type = None
                    if fight_detections:
                        event_type = "Violence"
                    elif fire_detections:
                        event_type = "Fire"
                    elif weapon_detections:
                        event_type = "Weapon"

                    if event_type:
                        current_time = time.time()
                        if current_time - self.last_event_time > self.cooldown_seconds:
                            self.last_event_time = current_time
                            
                            # Get snapshot of buffer safely
                            with self.frame_lock:
                                snapshot = list(self.frame_buffer)
                                
                            # Annotate the last frame in snapshot
                            if snapshot:
                                rec_frame = snapshot[-1].copy()
                                cv2.putText(rec_frame, f"ALERT: {event_type}", (50, 50),
                                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)
                                snapshot[-1] = rec_frame
                                
                            self.trigger_event(snapshot, event_type)

                    # Send Clean Frame (Binary)
                    try:
                        ret_enc, buffer = cv2.imencode('.jpg', frame)
                        if ret_enc:
                            await websocket.send(buffer.tobytes())
                    except Exception as e:
                        print(f"WS Send Image Error: {e}")
                        break # Break inner loop to reconnect

                    # Small sleep to yield to event loop
                    await asyncio.sleep(0.01)
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
        system.is_running = False
        system.cap.release()
