import cv2
import argparse
import socket
from ultralytics import YOLO
import supervision as sv
import numpy as np
import time
import threading
import sqlite3
import os
from flask import Flask, Response, jsonify, send_file
import base64
import io

app = Flask(__name__)

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Webcam")
    parser.add_argument("--resolution", default=[1280, 720], nargs=2, type=int, help="Resolution of the video stream")
    return parser.parse_args()

def initialize_video_capture(rtsp_url: str, resolution: tuple) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(0)
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

DATABASE = 'suspicious_objects.db'
if not os.path.exists(DATABASE):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''CREATE TABLE SuspiciousObjects (id INTEGER PRIMARY KEY, timestamp TEXT, image BLOB)''')
    conn.commit()
    conn.close()

def save_image_to_db(image):
    _, img_encoded = cv2.imencode('.jpg', image)
    img_bytes = img_encoded.tobytes()
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''INSERT INTO SuspiciousObjects (timestamp, image) VALUES (?, ?)''', (time.ctime(), img_bytes))
    conn.commit()
    conn.close()

def generate_frames(cap, model, box_annotator, label_annotator, esp32_ip, esp32_port, signal_cooldown):
    signal_sent = False
    suspicious_classes = [0, 1]
    allowed_classes = [2, 3, 4]
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        results = model(frame, agnostic_nms=True)[0]
        detections = sv.Detections.from_ultralytics(results)

        suspicious = detections[np.isin(detections.class_id, suspicious_classes)]
        allowed = detections[np.isin(detections.class_id, allowed_classes)]
        labels = [f"{model.model.names[int(class_id)]}" for class_id in detections.class_id]

        if len(suspicious) > 0 and len(allowed) == 0 and not signal_sent:
            message = 'a'
            threading.Thread(target=send_signal_to_esp32, args=(esp32_ip, esp32_port, message)).start()
            save_image_to_db(frame)  # Save image if suspicious
            signal_sent = True
            signal_reset_time = time.time() + signal_cooldown
        elif ((len(suspicious) == 0 and len(allowed) > 0) or (len(suspicious) > 0 and len(allowed) == 0)) and not signal_sent:
            message = 'b'
            threading.Thread(target=send_signal_to_esp32, args=(esp32_ip, esp32_port, message)).start()
            signal_sent = True
            signal_reset_time = time.time() + signal_cooldown

        if signal_sent and time.time() > signal_reset_time:
            signal_sent = False

        annotated_frame = box_annotator.annotate(scene=frame, detections=detections)
        label_annotator.annotate(scene=frame, detections=detections, labels=labels)
        ret, buffer = cv2.imencode('.jpg', annotated_frame)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/video')
def video_feed():
    args = parse_args()
    frame_width, frame_height = args.resolution

    rtsp_url = 'rtsp://admin:callmekiddo123@192.168.10.100/1'
    cap = initialize_video_capture(0, (frame_width, frame_height))

    model = YOLO('last_version.pt')
    box_annotator = sv.BoundingBoxAnnotator(thickness=2)
    label_annotator = sv.LabelAnnotator(text_thickness=2, text_scale=1)

    esp32_ip = '192.168.113.145'
    esp32_port = 8088
    signal_cooldown = 0.2

    return Response(generate_frames(cap, model, box_annotator, label_annotator, esp32_ip, esp32_port, signal_cooldown),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/images', methods=['GET'])
def get_images():
    conn = sqlite3.connect(database=DATABASE)
    c = conn.cursor()
    c.execute("SELECT id, timestamp, image FROM SuspiciousObjects")
    rows = c.fetchall()
    conn.close()

    images = []
    for row in rows:
        image_id = row[0]
        timestamp = row[1]
        image = row[2]
        encoded_image = base64.b64encode(image).decode('utf-8')
        images.append({"id": image_id, "timestamp": timestamp, "image": encoded_image})

    return jsonify(images)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
