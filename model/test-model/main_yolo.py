import argparse
import sys
import time
import requests
from collections import deque
from pathlib import Path

def main():
	parser = argparse.ArgumentParser(description="Webcam-only recorder: save 10s clip when NO person is detected (YOLO)")
	parser.add_argument("--model", default="yolo11n.pt", help="Path to YOLO .pt model (default: yolo11n.pt)")
	parser.add_argument("--conf", type=float, default=0.25, help="Confidence threshold for detections (default: 0.25)")
	parser.add_argument("--device", default=None, help="Device to run on, e.g. 'cpu' or '0' (default: autoselect)")
	parser.add_argument("--save-dir", default="recordings", help="Directory to save recorded clips")
	parser.add_argument("--buffer-seconds", type=float, default=10.0, help="Seconds to buffer for each clip (default: 10)")
	parser.add_argument("--stream-url", default="http://localhost:8000/push/cam1", help="URL to push frames to (default: .../push/cam1)")
	parser.add_argument("--camera-id", default="cam1", help="Camera ID (default: cam1)")
	parser.add_argument("--lat", type=str, default="0.0", help="Latitude (default: 0.0)")
	parser.add_argument("--long", type=str, default="0.0", help="Longitude (default: 0.0)")
	args = parser.parse_args()

	model_path = Path(args.model)
	if not model_path.exists():
		print(f"Model file not found: {model_path}\nPlace your model next to this script or provide --model path.")
		sys.exit(1)

	try:
		from ultralytics import YOLO
	except Exception:
		print("Missing dependency: ultralytics. Install from requirements.txt or run: python -m pip install ultralytics")
		raise

	try:
		import cv2
	except Exception:
		print("Missing dependency: opencv-python. Install from requirements.txt or run: python -m pip install opencv-python")
		raise

	print(f"Loading YOLO model: {model_path}")
	model = YOLO(str(model_path))
	
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

	# Determine person class index if available
	person_class = None
	try:
		if hasattr(model, 'names') and isinstance(model.names, (list, dict)):
			# model.names can be list or dict
			if isinstance(model.names, dict):
				for k, v in model.names.items():
					if str(v).lower() == 'person':
						person_class = int(k)
						break
			else:
				for i, v in enumerate(model.names):
					if str(v).lower() == 'person':
						person_class = i
						break
	except Exception:
		person_class = None

	print(f"Webcam opened {width}x{height} @ {fps} FPS, buffering {args.buffer_seconds}s ({buffer_size} frames).")
	print(f"Saving clips to: {save_dir}")
	print(f"Streaming to: {args.stream_url}")
	print(f"Mode: YOLO")
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

						results = model(frame, conf=args.conf, device=args.device or None)
						res = results[0]
						annotated_frame = res.plot()
						
						# YOLO Presence logic
						if hasattr(res, 'boxes') and res.boxes is not None:
							cls = None
							try:
								cls = res.boxes.cls
							except Exception:
								try:
									data = res.boxes.data
									if data is not None:
										cls = data[:, 5]
								except Exception:
									cls = None

							if cls is not None:
								try:
									arr = cls.cpu().numpy()
								except Exception:
									try:
										arr = cls.numpy()
									except Exception:
										arr = list(cls)

								for c in arr:
									if person_class is not None:
										if int(c) == int(person_class):
											presence = True
											break
									else:
										try:
											if int(c) < len(model.names) and str(model.names[int(c)]).lower() == 'person':
												presence = True
												break
										except Exception:
											pass
						
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
						out_path = save_dir / f"clip_no_person_{timestamp}_{clip_count}.mp4"
						fourcc = cv2.VideoWriter_fourcc(*'avc1')
						writer = cv2.VideoWriter(str(out_path), fourcc, fps, (width, height))
						print(f"No person detected — saving {args.buffer_seconds}s clip to {out_path}")
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
