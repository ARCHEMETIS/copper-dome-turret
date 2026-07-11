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
    """ตรวจจับด้วย YOLO + ประตูกัน ghost 2 ชั้น (ดู docs/vision-baseline.md)

    ชั้นขนาด: กรอบต้องมีขนาดที่ "เป็นไปได้" ตามสูตร ranging (ระยะ
    GATE_DIST_RANGE_MM แปลงเป็นช่วง √(w·h) ต่อ toy) — ghost บนเสื้อ/ผ้า
    มักใหญ่หรือเล็กผิดธรรมชาติ | ชั้นเวลา: ตัวนับสะสม +1 เมื่อเห็น -1
    เมื่อหาย ต้องถึง GATE_PERSIST_FRAMES ก่อนถึงยอมปล่อย detection —
    จากคลิปจริง ghost อยู่ทนสุด ~233ms (ไม่ถึง 3 เฟรมของ aiming loop)
    ส่วนตุ๊กตาจริงเจอ 96% ของเฟรมและหลุดทีละ 1-2 เฟรม การนับแบบสะสม
    (ไม่ reset เป็นศูนย์เมื่อหลุดเฟรมเดียว) เลยไม่หน่วงเป้าจริง"""

    def __init__(self):
        from ultralytics import YOLO  # import ตรงนี้ เพื่อให้โหมด hsv รันได้แม้ไม่ได้ลง ultralytics
        self.model = YOLO(config.YOLO_MODEL_PATH)
        self._persist = {}   # label -> ตัวนับสะสมการเห็นเป้า

    def _size_plausible(self, target, w, h, frame_w) -> bool:
        if config.FOCAL_PX is None:
            return True
        # normalize เป็น px ที่ความกว้าง FRAME_WIDTH (FOCAL_PX คาลิเบรตที่สเกลนั้น)
        size = (w * h) ** 0.5 * config.FRAME_WIDTH / frame_w
        real = config.TARGETS[target]["real_size_mm"]
        near, far = config.GATE_DIST_RANGE_MM
        return config.FOCAL_PX * real / far <= size <= config.FOCAL_PX * real / near

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

        if best is not None and not self._size_plausible(
                target, best.w_px, best.h_px, frame_bgr.shape[1]):
            best = None

        # ชั้นเวลา — นับสะสมต่อ label แล้วปล่อยเมื่อถึงเกณฑ์
        n = self._persist.get(target, 0)
        n = min(n + 1, config.GATE_PERSIST_FRAMES) if best is not None else max(n - 1, 0)
        self._persist[target] = n
        if best is not None and n < config.GATE_PERSIST_FRAMES:
            return None  # ยังไม่มั่นใจว่าไม่ใช่ ghost วูบเดียว
        return best


def get_detector():
    if config.DETECTOR == "yolo":
        return YoloDetector()
    return HsvDetector()
