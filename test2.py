import cv2
import argparse
import socket
from ultralytics import YOLO
import supervision as sv
import time
import threading
import numpy as np

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Webcam")
    parser.add_argument("--resolution", default=[1280, 720], nargs=2, type=int, help="Resolution of the video stream")
    return parser.parse_args()

def initialize_video_capture(rtsp_url: str, resolution: tuple) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(rtsp_url)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, resolution[0])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, resolution[1])
    return cap

def send_signal_to_esp32(ip: str, port: int, message: str):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((ip, port))
            s.sendall(message.encode('utf-8'))
            print("Signal sent successfully")
    except Exception as e:
        print(f"Error sending signal: {e}")

def main():
    args = parse_args()
    frame_width, frame_height = args.resolution

    rtsp_url = 'rtsp://admin:callmekiddo123@192.168.10.100/1'
    cap = initialize_video_capture(rtsp_url, (frame_width, frame_height))

    model = YOLO('v3.pt')
    box_annotator = sv.BoundingBoxAnnotator(thickness=2)
    label_annotator = sv.LabelAnnotator(text_thickness=2, text_scale=1)

    esp32_ip = '192.168.22.146'
    esp32_port = 8088
    message = 'D'
    signal_sent = False
    signal_cooldown = 15

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        results = model(frame, agnostic_nms=True)[0]
        detections = sv.Detections.from_ultralytics(results)

        selected_classes = [1, 3]
        person_detections = detections[np.isin(detections.class_id, selected_classes)]
        person_labels = [f"{model.model.names[int(class_id)]}" for class_id in person_detections.class_id]

        if len(person_detections) > 0 and not signal_sent:
            threading.Thread(target=send_signal_to_esp32, args=(esp32_ip, esp32_port, message)).start()
            signal_sent = True
            signal_reset_time = time.time() + signal_cooldown

        if signal_sent and time.time() > signal_reset_time:
            signal_sent = False

        annotated_frame = box_annotator.annotate(scene=frame, detections=person_detections)
        label_annotator.annotate(scene=frame, detections=person_detections, labels=person_labels)
        cv2.imshow("Person Detected", annotated_frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
