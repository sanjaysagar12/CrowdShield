from ultralytics import YOLO
import os

class FireDetector:
    def __init__(self, model_path=None):
        """
        Initialize the FireDetector model.
        
        Args:
            model_path (str): Path to the YOLO weights file. 
                              If None, defaults to 'yolov8/weights/best.pt' relative to this file.
        """
        if model_path is None:
            # Default path handling
            current_dir = os.path.dirname(os.path.abspath(__file__))
            model_path = os.path.join(current_dir, 'yolov8', 'yolon8.pt')
            
        print(f"Loading Fire Detection Model from: {model_path}")
        self.model = YOLO(model_path)
        
    def detect(self, frame, conf_threshold=0.4):
        """
        Detect fire in a frame.

        Args:
            frame (numpy.ndarray): Input image/frame.
            conf_threshold (float): Confidence threshold for detection.

        Returns:
            list: List of detections.
        """
        # Run inference
        results = self.model(frame, verbose=False)
        
        detections = []
        
        for result in results:
            boxes = result.boxes
            for box in boxes:
                conf = float(box.conf[0])
                
                if conf >= conf_threshold:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    cls_id = int(box.cls[0])
                    label = self.model.names[cls_id]
                    
                    detections.append({
                        "bbox": [x1, y1, x2, y2],
                        "confidence": conf,
                        "class_id": cls_id,
                        "label": label
                    })
        
        return detections
