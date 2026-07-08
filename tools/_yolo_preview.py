# =============================================================
# _yolo_preview.py — โค้ดที่ใช้ร่วมกันระหว่าง test_on_video.py / test_on_webcam.py
# ไม่ใช่สคริปต์ที่รันตรงๆ (ขึ้นต้นด้วย _) แค่ให้ทั้งสองไฟล์ import ไปใช้
# =============================================================
import sys
from pathlib import Path

import cv2
from ultralytics import YOLO

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import config


def load_model() -> YOLO:
    return YOLO(config.YOLO_MODEL_PATH)


def draw_detections(frame, model: YOLO):
    """รัน YOLO บน frame แล้ววาดกรอบ+ชื่อ+% ความมั่นใจทับลงไปตรงๆ (แก้ frame ในตัว)"""
    results = model.predict(frame, conf=config.YOLO_CONF, verbose=False)
    for box in results[0].boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        label = model.names[int(box.cls)]
        conf = float(box.conf)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
        cv2.putText(frame, f"{label} {conf:.0%}", (x1, max(25, y1 - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
    return frame
