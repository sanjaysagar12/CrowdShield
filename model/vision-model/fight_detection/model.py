from ultralytics import YOLO
import os

class FightDetector:
    def __init__(self, model_path=None):
        """
        Initialize the FightDetector model.
        
        Args:
            model_path (str): Path to the YOLO weights file. 
                              If None, defaults to 'yolov8/yolo_small_weights.pt' relative to this file.
        """
        if model_path is None:
            # Default path handling
            current_dir = os.path.dirname(os.path.abspath(__file__))
            model_path = os.path.join(current_dir, 'yolov8', 'yolos8.pt')
            
        print(f"Loading Fight Detection Model from: {model_path}")
        self.model = YOLO(model_path)
        # Class 1 is Violence/Fight according to README
        self.target_class_id = 1 

    def detect(self, frame, conf_threshold=0.4):
        """
        Detect fights in a frame.

        Args:
            frame (numpy.ndarray): Input image/frame.
            conf_threshold (float): Confidence threshold for detection.

        Returns:
            list: List of detections. Each detection is a dict/object or similar.
                  For now returning the raw result object wrapper or a simplified list.
        """
        # Run inference
        results = self.model(frame, verbose=False)
        
        detections = []
        
        for result in results:
            boxes = result.boxes
            for box in boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                
                # Check if it matches the fight class and confidence threshold
                if cls_id == self.target_class_id and conf >= conf_threshold:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    detections.append({
                        "bbox": [x1, y1, x2, y2],
                        "confidence": conf,
                        "class_id": cls_id,
                        "label": "Violence"
                    })
        
        return detections
