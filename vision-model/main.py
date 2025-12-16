

import argparse
import os
import sys
import time
from collections import deque
from pathlib import Path

def main():
	parser = argparse.ArgumentParser(description="Webcam-only recorder: save 10s clip when NO person is detected")
	parser.add_argument("--model", default="yolo11n.pt", help="Path to YOLO .pt model (default: yolo11n.pt)")
	parser.add_argument("--conf", type=float, default=0.25, help="Confidence threshold for detections (default: 0.25)")
	parser.add_argument("--device", default=None, help="Device to run on, e.g. 'cpu' or '0' (default: autoselect)")
	parser.add_argument("--save-dir", default="recordings", help="Directory to save recorded clips")
	parser.add_argument("--buffer-seconds", type=float, default=10.0, help="Seconds to buffer for each clip (default: 10)")
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

	model = YOLO(str(model_path))
	save_dir = Path(args.save_dir)
	save_dir.mkdir(parents=True, exist_ok=True)

	# Open webcam
	cap = cv2.VideoCapture(0)
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

	last_presence = True
	clip_count = 0

	try:
		while True:
			ret, frame = cap.read()
			if not ret:
				print("Webcam frame read failed, exiting")
				break

			frame_buffer.append(frame.copy())

			# Run detection on this frame
			try:
				results = model(frame, conf=args.conf, device=args.device or None)
				res = results[0]
			except Exception as e:
				# If model call fails, skip this frame
				print(f"Model inference error: {e}")
				time.sleep(0.01)
				continue

			# Determine if any 'person' detected
			presence = False
			try:
				if hasattr(res, 'boxes') and res.boxes is not None:
					# Attempt to read class indices from boxes
					cls = None
					try:
						cls = res.boxes.cls
					except Exception:
						try:
							# fallback: boxes.data columns [x1,y1,x2,y2,conf,class]
							data = res.boxes.data
							if data is not None:
								cls = data[:, 5]
						except Exception:
							cls = None

					if cls is not None:
						# convert to python iterable
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
								# if we don't know class index, try matching by name using model.names
								try:
									if int(c) < len(model.names) and str(model.names[int(c)]).lower() == 'person':
										presence = True
										break
								except Exception:
									pass
			except Exception:
				presence = False

			# Trigger: when presence goes from True -> False and buffer is full
			if not presence and last_presence and len(frame_buffer) == buffer_size:
				timestamp = time.strftime('%Y%m%d_%H%M%S')
				out_path = save_dir / f"clip_no_person_{timestamp}_{clip_count}.mp4"
				fourcc = cv2.VideoWriter_fourcc(*'mp4v')
				writer = cv2.VideoWriter(str(out_path), fourcc, fps, (width, height))
				print(f"No person detected — saving {args.buffer_seconds}s clip to {out_path}")
				for f in frame_buffer:
					writer.write(f)
				writer.release()
				clip_count += 1
				last_presence = False

			if presence:
				last_presence = True

			# Small sleep to avoid tight loop; inference determines effective rate
			time.sleep(0.001)

	finally:
		cap.release()

if __name__ == "__main__":
	main()

