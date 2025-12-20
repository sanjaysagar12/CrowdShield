
import argparse
import sys
import time
import requests
from collections import deque
from pathlib import Path

def main():
	parser = argparse.ArgumentParser(description="Webcam-only recorder: save 10s clip when NO person is detected (Teachable Machine)")
	parser.add_argument("--save-dir", default="recordings", help="Directory to save recorded clips")
	parser.add_argument("--buffer-seconds", type=float, default=10.0, help="Seconds to buffer for each clip (default: 10)")
	parser.add_argument("--stream-url", default="http://localhost:8000/push/cam1", help="URL to push frames to (default: .../push/cam1)")
	parser.add_argument("--camera-id", default="cam1", help="Camera ID (default: cam1)")
	parser.add_argument("--lat", type=str, default="0.0", help="Latitude (default: 0.0)")
	parser.add_argument("--long", type=str, default="0.0", help="Longitude (default: 0.0)")
	parser.add_argument("--tm-model", default="converted_keras/keras_model.h5", help="Path to TM .h5 model")
	parser.add_argument("--tm-labels", default="converted_keras/labels.txt", help="Path to TM labels file")
	args = parser.parse_args()

	tm_model = None
	tm_labels = []

	# Teachable Machine setup
	tm_model_path = Path(args.tm_model)
	tm_labels_path = Path(args.tm_labels)
	
	if not tm_model_path.exists():
		print(f"TM model file not found: {tm_model_path}")
		sys.exit(1)
	if not tm_labels_path.exists():
		print(f"TM labels file not found: {tm_labels_path}")
		sys.exit(1)

	try:
		import cv2
		import numpy as np
		from PIL import Image, ImageOps
		try:
			# Try using tf_keras (legacy bridge) first for better H5 compatibility
			from tf_keras.models import load_model
		except ImportError:
			# Fallback to standard keras (might be Keras 3)
			from tensorflow.keras.models import load_model
	except ImportError as e:
		print(f"Missing dependency for Teachable Machine: {e}")
		print("Ensure tensorflow, tf-keras, numpy, and pillow are installed.")
		sys.exit(1)

	print(f"Loading Teachable Machine model: {tm_model_path}")
	# Compile=False is standard for TM models as we only predict
	tm_model = load_model(str(tm_model_path), compile=False)
	
	with open(tm_labels_path, "r") as f:
		tm_labels = f.readlines()
	
	print(f"Loaded {len(tm_labels)} labels.")

	save_dir = Path(args.save_dir)
	save_dir.mkdir(parents=True, exist_ok=True)

	# Open webcam
	# Use CAP_DSHOW to avoid MSMF errors on Windows
	cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
	if not cap.isOpened():
		print("Failed to open webcam (device 0)")
		sys.exit(1)

	fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
	try:
		fps = float(fps)
		if fps <= 1.0:
			fps = 30.0
	except Exception:
		fps = 30.0

	width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 640)
	height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 480)

	buffer_size = max(1, int(round(fps * float(args.buffer_seconds))))
	frame_buffer = deque(maxlen=buffer_size)

	print(f"Webcam opened {width}x{height} @ {fps} FPS, buffering {args.buffer_seconds}s ({buffer_size} frames).")
	print(f"Saving clips to: {save_dir}")
	print(f"Streaming to: {args.stream_url}")
	print(f"Mode: Teachable Machine")
	print(f"Camera ID: {args.camera_id}, Location: {args.lat}, {args.long}")

	# Parse stream URL to get websocket URL if needed, or assume argument provided is correct base
	# If args.stream_url is http, convert to ws for the websocket connection
	ws_url = args.stream_url.replace("http://", "ws://").replace("https://", "wss://")
	if "/push/" in ws_url and "/ws/" not in ws_url:
             ws_url = ws_url.replace("/push/", "/ws/push/")
	
	print(f"WebSocket URL: {ws_url}")

	import asyncio
	try:
		import websockets
	except ImportError:
		print("Missing dependency: websockets. Install with: pip install websockets")
		sys.exit(1)

	async def run_loop():
		last_presence = True
		clip_count = 0
		
		# Connect to WebSocket
		try:
			async with websockets.connect(ws_url) as websocket:
				print("Connected to WebSocket server")
				
				while True:
					ret, frame = cap.read()
					if not ret:
						print("Webcam frame read failed, exiting")
						break

					frame_buffer.append(frame.copy())

					# Run detection
					try:
						annotated_frame = frame.copy()
						presence = False

						# Teachable Machine Logic
						# Preprocess: CV2(BGR) -> PIL(RGB) -> Resize -> Normalize
						rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
						pil_image = Image.fromarray(rgb_frame)
						
						# Resize and crop to 224x224
						size = (224, 224)
						pil_image = ImageOps.fit(pil_image, size, Image.Resampling.LANCZOS)
						
						image_array = np.asarray(pil_image)
						normalized_image_array = (image_array.astype(np.float32) / 127.5) - 1
						
						data = np.ndarray(shape=(1, 224, 224, 3), dtype=np.float32)
						data[0] = normalized_image_array
						
						prediction = tm_model.predict(data, verbose=0)
						index = np.argmax(prediction)
						confidence_score = prediction[0][index]
						
						predicted_label_line = tm_labels[index] # e.g. "0 YES\n"
						class_name = predicted_label_line.strip()
						
						# Draw on frame for debug
						cv2.putText(annotated_frame, f"TM: {class_name} ({confidence_score:.2f})", (10, 30), 
								   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

						# Logic: Normal -> Safe (presence=True), Fire/Violence -> Trigger (presence=False)
						if "Normal" in class_name:
							presence = True
						elif "Fire" in class_name or "Violence" in class_name:
							presence = False
						
						# Push frame via WebSocket
						try:
							ret, buffer = cv2.imencode('.jpg', annotated_frame)
							if ret:
								await websocket.send(buffer.tobytes())
						except Exception as e:
							print(f"WS Send error: {e}")
							# Break to trigger reconnect logic if critical, or just pass
							# For now, let's try to ignore single frame errors but if socket closed it will raise

					except Exception as e:
						print(f"Inference/Send error: {e}")
						# Allow loop to continue (maybe model error), but sleep a bit
						await asyncio.sleep(0.01)

					# Recording logic
					if not presence and last_presence and len(frame_buffer) == buffer_size:
						timestamp = time.strftime('%Y%m%d_%H%M%S')
						out_path = save_dir / f"clip_event_{timestamp}_{clip_count}.mp4"
						fourcc = cv2.VideoWriter_fourcc(*'avc1')
						writer = cv2.VideoWriter(str(out_path), fourcc, fps, (width, height))
						print(f"Fire/Violence detected — saving {args.buffer_seconds}s clip to {out_path}")
						for f in frame_buffer:
							writer.write(f)
						writer.release()
						
						
						# Upload to agent in a separate thread
						def upload_worker(path, cam_id, lat, long):
							try:
								print(f"Sending {path.name} to agent...")
								with open(path, 'rb') as f:
									files = {'file': (path.name, f, 'video/mp4')}
									data_payload = {
										'camera_id': cam_id,
										'latitude': lat,
										'longitude': long
									}
									response = requests.post('http://localhost:8001/agent', files=files, data=data_payload)
									if response.status_code == 200:
										print(f"Successfully sent {path.name} to agent.")
									else:
										print(f"Failed sent {path.name}. Status: {response.status_code}")
							except Exception as e:
								print(f"Error sending to agent: {e}")

						import threading
						upload_thread = threading.Thread(
							target=upload_worker, 
							args=(out_path, args.camera_id, args.lat, args.long)
						)
						upload_thread.start()

						clip_count += 1
						last_presence = False

					if presence:
						last_presence = True

					await asyncio.sleep(0.001)

		except (websockets.exceptions.ConnectionClosedError, ConnectionRefusedError) as e:
			print(f"WebSocket connection failed/closed: {e}. Retrying in 5s...")
			await asyncio.sleep(5)
			# Recursive retry or loop
			# Simple way: just return and let main loop handle it if we structured it that way
			# Ideally we want a while True loop around the connection
			raise e

	# Main execution wrapper
	async def main_async():
		while True:
			try:
				await run_loop()
			except Exception as e:
				print(f"Restarting loop due to: {e}")
				await asyncio.sleep(5)
				
	try:
		asyncio.run(main_async())
	finally:
		cap.release()

if __name__ == "__main__":
	main()
