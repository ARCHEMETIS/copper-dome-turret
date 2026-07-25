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


# แมป yolo_class (เลข class ตอนเทรน) กลับเป็น target key — ใช้ตอน detect_all
_YOLO_CLASS_TO_TARGET = {t["yolo_class"]: key for key, t in config.TARGETS.items()}

# imgsz ของเส้นทางเล็ง/ตัดสินยิง (detect) — เท่ากับ default เดิมของ ultralytics
# แต่เขียนให้ชัดเพื่อให้ warmup อุ่นขนาดเดียวกันได้ (ถ้าปล่อยเป็น default แล้ว
# ultralytics เปลี่ยนค่า จะอุ่นผิดขนาดโดยไม่มีใครรู้). จอใช้ YOLO_DISPLAY_IMGSZ
_AIM_IMGSZ = 640


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

    def detect_all(self, frame_bgr) -> list[Detection]:
        """หาทุกเป้าที่เห็นในเฟรม (1 ตัวต่อชนิด) — ให้ UI คลิกเลือกได้
        เป้า 3 ตัวเป็นคนละสี/คนละคลาส จึงวนหาแยกทีละชนิดพอ"""
        out = []
        for target in config.TARGETS:
            det = self.detect(frame_bgr, target)
            if det is not None:
                out.append(det)
        return out

    # HSV ไม่มีประตูเวลา — มีเมธอดพวกนี้ไว้ให้ interface เหมือน YoloDetector
    # ผู้เรียก (aiming/main_click) จะได้ไม่ต้องเช็คชนิด detector
    def reset_persist(self, target: str | None = None):
        pass

    def warming_up(self, target: str) -> bool:
        return False


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
        import torch
        self.model = YOLO(config.YOLO_MODEL_PATH)
        # ใช้ GPU ถ้ามี — ultralytics ไม่ auto ไป CUDA ให้ ต้องสั่งเอง ไม่งั้นตกไป
        # CPU (~42ms/เฟรม) ทำจอมอนิเตอร์แล็ค. ย้ายโมเดลค้างบน GPU + warmup ครั้งเดียว
        self.device = 0 if torch.cuda.is_available() else "cpu"
        self.model.to(self.device)
        self._persist = {}   # label -> ตัวนับสะสมการเห็นเป้า
        self._last_box = {}  # label -> (cx, cy, w, h) ของกรอบที่นับไว้เฟรมก่อน

        # warmup จริง (23 ก.ค.) — คอมเมนต์ข้างบนอ้างมาตลอดว่ามี แต่โค้ดไม่เคยมี
        # ต้องอุ่น "ทั้งสองขนาด" เพราะระบบใช้คนละ imgsz กัน (จอ 512 / เล็ง 640)
        # และ CUDA คอมไพล์เคอร์เนลแยกตามขนาด — ไม่อุ่น = เรียกครั้งแรกของแต่ละขนาด
        # ช้ากว่าปกติหลายเท่า (นัดแรกอืด + ค่าที่จับเวลาตอนจูนเป็น outlier)
        blank = np.zeros((config.FRAME_HEIGHT, config.FRAME_WIDTH, 3), dtype=np.uint8)
        for imgsz in (config.YOLO_DISPLAY_IMGSZ, _AIM_IMGSZ):
            self.model.predict(blank, imgsz=imgsz, verbose=False, device=self.device)

    def _size_plausible(self, target, w, h, frame_w) -> bool:
        if config.FOCAL_PX is None:
            return True
        # normalize เป็น px ที่ความกว้าง FRAME_WIDTH (FOCAL_PX คาลิเบรตที่สเกลนั้น)
        size = (w * h) ** 0.5 * config.FRAME_WIDTH / frame_w
        real = config.TARGETS[target]["real_size_mm"]
        near, far = config.GATE_DIST_RANGE_MM
        return config.FOCAL_PX * real / far <= size <= config.FOCAL_PX * real / near

    def detect_all(self, frame_bgr) -> list[Detection]:
        """หาทุกเป้าในเฟรมทีเดียว (predict รอบเดียว) — ให้ UI คลิกเลือกได้

        ต่างจาก detect(): ไม่กรองด้วยประตูเวลา (temporal gate) เพราะประตูนั้น
        นับสะสมต่อ "ชนิดเป้าเดียว" ไว้ตัดสินใจตอนเล็ง/ยิง ส่วนจอมอนิเตอร์แค่
        โชว์กรอบ — ผีวูบ 1 เฟรมยอมรับได้ คนดูเลือกตัวจริงเองอยู่แล้ว และตอน
        กดยิงจริง aim_at() เรียก detect() ที่มีประตูครบกันไว้อีกชั้น
        ยังกรองด้วยชั้นขนาด (size sanity) เพื่อตัดผีกรอบใหญ่/เล็กผิดธรรมชาติ"""
        results = self.model.predict(frame_bgr, conf=config.YOLO_DISPLAY_CONF, verbose=False,
                                     device=self.device, imgsz=config.YOLO_DISPLAY_IMGSZ)
        out = []
        for box in results[0].boxes:
            target = _YOLO_CLASS_TO_TARGET.get(int(box.cls))
            if target is None:
                continue
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            w, h = x2 - x1, y2 - y1
            if not self._size_plausible(target, w, h, frame_bgr.shape[1]):
                continue
            out.append(Detection(target, (x1 + x2) / 2, (y1 + y2) / 2,
                                  w, h, float(box.conf)))
        return out

    def reset_persist(self, target: str | None = None):
        """ล้างตัวนับประตูเวลา — ต้องเรียกตอน "เริ่มล็อกเป้าใหม่"

        ไม่ล้าง = ตัวนับค้างที่ 3 จากการล็อกครั้งก่อน แล้วการล็อกรอบถัดไปของ
        ตุ๊กตาตัวเดิมจะผ่านประตูตั้งแต่เฟรมแรก (ghost ก็ผ่านด้วย) = ประตูหายไปเฉยๆ
        (Codex เจอ 23 ก.ค. reproduce แล้ว: session แรก False,False,True /
        session ถัดไปเฟรมแรก True เลย)"""
        if target is None:
            self._persist.clear()
            self._last_box.clear()
        else:
            self._persist.pop(target, None)
            self._last_box.pop(target, None)

    @staticmethod
    def _same_object(prev, det) -> bool:
        """กรอบใหม่เป็น "ของชิ้นเดิม" กับที่นับไว้เฟรมก่อนไหม — วัดจากระยะจุดกึ่งกลาง

        เผื่อไว้กว้างโดยตั้งใจ เพราะระหว่างสองเฟรมป้อมหมุนได้ถึง AIM_MAX_STEP_DEG
        และกล้องติดอยู่บนลำกล้อง = เป้าจริงเลื่อนทั้งเฟรมตามไปด้วย ประตูนี้มีไว้
        ตัดผีที่ "กระโดดข้ามจอ" ไม่ใช่ไว้ track แบบละเอียด"""
        pcx, pcy, pw, ph = prev
        allow = max(config.GATE_JUMP_FRAC * max(pw, ph), config.GATE_JUMP_MIN_PX)
        return ((det.cx - pcx) ** 2 + (det.cy - pcy) ** 2) ** 0.5 <= allow

    def detect(self, frame_bgr, target: str) -> Detection | None:
        want = config.TARGETS[target]["yolo_class"]
        results = self.model.predict(frame_bgr, conf=config.YOLO_CONF, verbose=False,
                                     device=self.device, imgsz=_AIM_IMGSZ)
        best = None
        for box in results[0].boxes:
            if int(box.cls) != want:
                continue
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            w, h = x2 - x1, y2 - y1
            # ⚠ กรองขนาด "ทุกกล่อง" ก่อนเลือกตัวชนะ — ห้ามเลือกก่อนแล้วค่อยกรอง
            # (Codex เจอ 23 ก.ค.) เดิม: ghost ตัวใหญ่ conf 0.95 ชนะเป้าจริง conf 0.80
            # แล้วโดนประตูขนาดตัดทิ้งทีหลัง → คืน None ทั้งที่เป้าจริงอยู่ในเฟรม
            # = ghost หนึ่งตัวกลบเป้าจริงได้ทั้งเฟรม
            if not self._size_plausible(target, w, h, frame_bgr.shape[1]):
                continue
            conf = float(box.conf)
            if best is None or conf > best.conf:
                best = Detection(target, (x1 + x2) / 2, (y1 + y2) / 2, w, h, conf)

        # ชั้นเวลา+ตำแหน่ง — นับสะสมเฉพาะตอนที่เป็น "ของชิ้นเดิม" ติดกัน
        # (เดิมนับแค่ label: ผีคนละตัวคนละมุมจอ 3 เฟรมก็ครบเกณฑ์ได้ ดู GATE_JUMP_* ใน config)
        n = self._persist.get(target, 0)
        if best is None:
            n = max(n - 1, 0)
            if n == 0:
                self._last_box.pop(target, None)
        else:
            prev = self._last_box.get(target)
            if prev is None or self._same_object(prev, best):
                n = min(n + 1, config.GATE_PERSIST_FRAMES)
            else:
                n = 1   # คนละชิ้นกับที่นับอยู่ — เริ่มนับใหม่จากกรอบนี้ ไม่ใช่สะสมต่อ
            self._last_box[target] = (best.cx, best.cy, best.w_px, best.h_px)
        self._persist[target] = n
        if best is not None and n < config.GATE_PERSIST_FRAMES:
            return None  # ยังไม่มั่นใจว่าไม่ใช่ ghost วูบเดียว
        return best

    def warming_up(self, target: str) -> bool:
        """True = "ยังนับเฟรมไม่ครบ" ไม่ใช่ "ไม่มีเป้า" — ให้ผู้เรียกแยกสองเคสนี้ออก
        (aiming ใช้ตัดสินว่าจะกวาดหาเป้าหรือแค่รออีกเฟรม)"""
        return 0 < self._persist.get(target, 0) < config.GATE_PERSIST_FRAMES


def get_detector():
    if config.DETECTOR == "yolo":
        return YoloDetector()
    return HsvDetector()
