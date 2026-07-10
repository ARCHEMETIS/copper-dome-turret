# =============================================================
# _yolo_preview.py — โค้ดที่ใช้ร่วมกันระหว่าง test_on_video.py / test_on_webcam.py
# ไม่ใช่สคริปต์ที่รันตรงๆ (ขึ้นต้นด้วย _) แค่ให้ทั้งสองไฟล์ import ไปใช้
# =============================================================
import statistics
import sys
from collections import defaultdict, deque
from pathlib import Path

import cv2
from ultralytics import YOLO

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import config

# กรอบ YOLO สั่น ±ไม่กี่ px ทุกเฟรม แต่ที่ระยะไกลกรอบแคบ 1 px ≈ 1 cm
# → ระยะดิบเด้งตลอด เก็บย้อนหลังต่อ class แล้วโชว์ median แทน (นิ่งขึ้นมาก
# และทนค่าหลุดโดดๆ ได้ดีกว่า average)
_DIST_SMOOTH_FRAMES = 9
_dist_hist: dict[str, deque] = defaultdict(lambda: deque(maxlen=_DIST_SMOOTH_FRAMES))


def load_model() -> YOLO:
    return YOLO(config.YOLO_MODEL_PATH)


def draw_detections(frame, model: YOLO):
    """รัน YOLO บน frame แล้ววาดกรอบ+ชื่อ+% ความมั่นใจ+ระยะ ทับลงไปตรงๆ (แก้ frame ในตัว)"""
    results = model.predict(frame, conf=config.YOLO_CONF, verbose=False)
    # FOCAL_PX คาลิเบรตที่ความกว้างเฟรม FRAME_WIDTH — ถ้าเฟรมจริงกว้างไม่เท่า
    # (เช่นกล้องโน้ตบุ๊ก 640px) ต้องสเกล focal ตาม ไม่งั้นระยะเพี้ยนเป็นเท่าตัว
    focal = None
    if config.FOCAL_PX is not None:
        focal = config.FOCAL_PX * frame.shape[1] / config.FRAME_WIDTH
    seen_labels = set()
    for box in results[0].boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        label = model.names[int(box.cls)]
        conf = float(box.conf)
        text = f"{label} {conf:.0%}"
        if focal is not None and label in config.TARGETS and x2 > x1 and y2 > y1:
            # √(w·h) ตัวเดียวกับ ranging.py — ทนตุ๊กตาหันเฉียง/นอน/หงายท้อง
            size_px = ((x2 - x1) * (y2 - y1)) ** 0.5
            dist_cm = focal * config.TARGETS[label]["real_size_mm"] / size_px / 10
            _dist_hist[label].append(dist_cm)
            seen_labels.add(label)
            text += f" {statistics.median(_dist_hist[label]):.0f}cm"
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
        cv2.putText(frame, text, (x1, max(25, y1 - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

    # เป้าที่หายจากเฟรม = ถูกย้าย/ถูกบัง — ทิ้งประวัติระยะของมัน ไม่งั้นตอน
    # โผล่กลับมา median จะปนค่าจากตำแหน่งเก่าไปอีกหลายเฟรม
    for label in [k for k in _dist_hist if k not in seen_labels]:
        del _dist_hist[label]
    return frame
