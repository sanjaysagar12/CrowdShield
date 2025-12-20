import cv2
import sys
import os

# Add the current directory to sys.path to ensure imports work correctly
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from fight_detection.model import FightDetector
from weapon_detection.model import WeaponDetector

def main():
    # Initialize Detectors
    fight_detector = FightDetector()
    weapon_detector = WeaponDetector()
    
    # Open the webcam (index 1 for OBS Virtual Camera)
    cap = cv2.VideoCapture(1)
    
    if not cap.isOpened():
        print("Error: Could not open video capture (1). Trying 0...")
        cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
         print("Error: Could not open any camera.")
         return

    print("Press 'q' to quit.")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Could not read frame.")
            break

        # Run Detections
        fight_detections = fight_detector.detect(frame)
        weapon_detections = weapon_detector.detect(frame, conf_threshold=0.4)

        # Draw Fight Detections (Red)
        for det in fight_detections:
            x1, y1, x2, y2 = map(int, det['bbox'])
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
            cv2.putText(frame, f"{det['label']} {det['confidence']:.2f}", (x1, y1 - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

        # Draw Weapon Detections (Blue)
        for det in weapon_detections:
            x1, y1, x2, y2 = map(int, det['bbox'])
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
            cv2.putText(frame, f"{det['label']} {det['confidence']:.2f}", (x1, y1 - 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

        # Show the frame
        cv2.imshow("Vision Model Test", frame)

        # Quit on 'q' press
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
