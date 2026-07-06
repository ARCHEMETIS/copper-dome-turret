# =============================================================
# detector.py — ตรวจจับตุ๊กตาในภาพ มี 2 ทาง:
#   HsvDetector  : แยกด้วยสี ใช้ได้ทันที ไม่ต้องเทรน (แต่คาปิบาร่า/ช้างเสี่ยง)
#   YoloDetector : YOLOv8 เทรนจากรูปจริง (ทางหลัก แม่นกว่า)
# สลับด้วย config.DETECTOR — interface เหมือนกัน โค้ดส่วนอื่นไม่ต้องแก้
# =============================================================
from dataclasses import dataclass

import cv2
import numpy as np

import config


@dataclass
class Detection:
    label: str        # "dino" / "capybara" / "elephant"
    cx: float         # จุดกึ่งกลางกรอบ (pixel)
    cy: float
    w_px: float       # ความกว้างกรอบ (ใช้วัดระยะ)
    h_px: float
    conf: float


class HsvDetector:
    """หา 1 เป้าที่ระบุ ด้วยช่วงสี HSV จาก config"""

    def detect(self, frame_bgr, target: str) -> Detection | None:
        t = config.TARGETS[target]
        hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array(t["hsv_lower"]), np.array(t["hsv_upper"]))
        # ลบ noise เม็ดเล็กๆ
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        biggest = max(contours, key=cv2.contourArea)
        if cv2.contourArea(biggest) < config.HSV_MIN_AREA_PX:
            return None
        x, y, w, h = cv2.boundingRect(biggest)
        return Detection(target, x + w / 2, y + h / 2, w, h, conf=1.0)


class YoloDetector:
    def __init__(self):
        from ultralytics import YOLO  # import ตรงนี้ เพื่อให้โหมด hsv รันได้แม้ไม่ได้ลง ultralytics
        self.model = YOLO(config.YOLO_MODEL_PATH)

    def detect(self, frame_bgr, target: str) -> Detection | None:
        want = config.TARGETS[target]["yolo_class"]
        results = self.model.predict(frame_bgr, conf=config.YOLO_CONF, verbose=False)
        best = None
        for box in results[0].boxes:
            if int(box.cls) != want:
                continue
            if best is None or float(box.conf) > best.conf:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                best = Detection(
                    target, (x1 + x2) / 2, (y1 + y2) / 2,
                    x2 - x1, y2 - y1, float(box.conf),
                )
        return best


def get_detector():
    if config.DETECTOR == "yolo":
        return YoloDetector()
    return HsvDetector()
