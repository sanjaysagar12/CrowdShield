# Simple YOLO Webcam Recorder

This repository contains a simple webcam recorder that uses the provided `yolo11n.pt` YOLO model to run real-time detection on the webcam. The script keeps a rolling buffer (default 10 seconds) and will save a 10-second MP4 clip when NO person is detected (on the transition from person-present to no-person).

Usage:

```bash
# Run the webcam recorder (uses device 0)
python main.py
```

Options:

- `--model`: path to model file (default: `yolo11n.pt`)
- `--conf`: confidence threshold for detections (default: `0.25`)
- `--device`: device to run on, e.g. `cpu` or `0` for first GPU
- `--save-dir`: directory to save recorded clips (default: `recordings`)
- `--buffer-seconds`: seconds to buffer for each clip (default: `10.0`)

Install requirements:

```bash
python -m pip install -r requirements.txt
```

Behavior and notes:

- The script opens the system webcam (device 0) and runs YOLO on each frame.
- A rolling buffer of `--buffer-seconds` is maintained; when the detector transitions from detecting a person to detecting no person and the buffer is full, the buffer is written to an MP4 file.
- Saved files are named like `clip_no_person_YYYYMMDD_HHMMSS_N.mp4` and written to `--save-dir` (default `recordings`).
- Ensure `yolo11n.pt` is present in the working directory or pass `--model` with the correct path.
- The script requires `ultralytics` and `opencv-python` (see `requirements.txt`).

If you want different trigger logic (e.g., save when a person is detected, or record the next 10 seconds instead of the previous 10 seconds), I can update the script accordingly.
