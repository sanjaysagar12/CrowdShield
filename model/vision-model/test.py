import cv2
import sys
import os

# Add the current directory to sys.path to ensure imports work correctly
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from fight_detection.model import FightDetector

def main():
    # Initialize the fight detector
    detector = FightDetector()
    
    # Open the webcam (index 1 for OBS Virtual Camera)
    cap = cv2.VideoCapture(1)
    
    if not cap.isOpened():
        print("Error: Could not open video capture.")
        return

    print("Press 'q' to quit.")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Could not read frame.")
            break

        # Detect fights
        detections = detector.detect(frame)

        # Draw detections
        for det in detections:
            bbox = det['bbox']
            confidence = det['confidence']
            label = det['label']
            
            x1, y1, x2, y2 = map(int, bbox)
            
            # Draw bounding box (Red for violence)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
            
            # Draw label
            text = f"{label}: {confidence:.2f}"
            cv2.putText(frame, text, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

        # Show the frame
        cv2.imshow("Fight Detection Test", frame)

        # Quit on 'q' press
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
