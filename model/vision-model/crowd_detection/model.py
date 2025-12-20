from ultralytics import YOLO
import os

class CrowdDetector:
    def __init__(self, model_path=None):
        """
        Initialize the CrowdDetector model.
        
        Args:
            model_path (str): Path to the YOLO weights file. 
                              If None, use 'yolov8n.pt' which will be downloaded automatically.
        """
        if model_path is None:
            model_path = os.path.join(os.path.dirname(__file__), 'yolo', 'yolov8n.pt')
            
        print(f"Loading Crowd Detection Model from: {model_path}")
        self.model = YOLO(model_path)
        
    def detect(self, frame, conf_threshold=0.5):
        """
        Detect people in a frame.

        Args:
            frame (numpy.ndarray): Input image/frame.
            conf_threshold (float): Confidence threshold for detection.

        Returns:
            list: List of detections (only persons).
        """
        # Run inference, filtering for class 0 (person)
        # classes=0 argument creates a filter
        results = self.model(frame, classes=0, verbose=False)
        
        detections = []
        
        for result in results:
            boxes = result.boxes
            for box in boxes:
                conf = float(box.conf[0])
                
                if conf >= conf_threshold:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    cls_id = int(box.cls[0])
                    # Ensure it is a person (redundant if classes=0 used but safe)
                    if cls_id == 0:
                        label = "Person"
                        
                        detections.append({
                            "bbox": [x1, y1, x2, y2],
                            "confidence": conf,
                            "class_id": cls_id,
                            "label": label
                        })
        
        return detections
