# =============================================================
# capture_negatives.py — ถ่ายรูป "ฉากหลังเปล่า" (ไม่มีตุ๊กตา) เข้าเทรนเซ็ต
#
# ทำไม: เทรนเซ็ตตอนนี้ทุกรูปมีตุ๊กตา (0 รูป background) โมเดลเลยไม่เคยเรียนรู้
# ว่า "เสื้อขาว/คน/ฉากหลัง = ไม่ใช่เป้า" → เกิด ghost detection
# Ultralytics แนะนำ background ~10% ของเทรนเซ็ต (~100 รูปสำหรับชุดนี้)
#
# วิธีใช้:
#   venv\Scripts\python.exe tools\capture_negatives.py
#
# ⚠ กติกาเดียวที่ห้ามพลาด: **ห้ามมีตุ๊กตาทั้ง 3 ตัวอยู่ในเฟรมเด็ดขาด**
# ถ้ามีตุ๊กตาแล้วเซฟเป็น negative = สอนโมเดลว่า "ตุ๊กตา = ไม่ใช่เป้า" (พังหนักกว่าเดิม)
#
# เคล็ดลับให้ได้ negative คุณภาพสูงสุด: จอจะโชว์กรอบเหลือง = จุดที่โมเดล
# "เห็นผี" อยู่ตอนนี้ (conf ต่ำๆ ก็โชว์) — จงใจถ่ายเฟรมพวกนั้นเยอะๆ
# (เสื้อขาว เสื้อเทา คนเดินผ่าน โต๊ะ ฉากสนาม) เพราะเป็นตัวอย่างที่แก้นิสัย
# โมเดลได้ตรงจุดสุด (hard negative)
#
# รูปจะถูกเซฟเข้า dataset/train/images + label เปล่าใน dataset/train/labels
# (ชื่อขึ้นต้น bg_ ลบทิ้งง่ายถ้าถ่ายพลาด) — เสร็จแล้วเทรนใหม่ได้เลย
# =============================================================
import sys
import time
from pathlib import Path

import cv2

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

import camera
import config

IMG_DIR = _ROOT / "dataset" / "train" / "images"
LBL_DIR = _ROOT / "dataset" / "train" / "labels"
GHOST_CONF = 0.15           # โชว์แม้ conf ต่ำ — ให้เห็นว่าโมเดลแอบเห็นผีตรงไหน


def main():
    from ultralytics import YOLO
    model = YOLO(config.YOLO_MODEL_PATH)

    cap = camera.open_camera()
    count = sum(1 for _ in IMG_DIR.glob("bg_*.jpg"))
    print("SPACE = ถ่าย 1 รูป | a = ถ่ายอัตโนมัติทุก 1 วิ (กดอีกทีหยุด) | q = ออก")
    print(f"มี negative อยู่แล้ว {count} รูป (เป้าหมาย ~100)")
    print("⚠ เก็บตุ๊กตาทั้ง 3 ตัวออกนอกเฟรมก่อนถ่ายทุกครั้ง!")

    auto = False
    last_auto = 0.0
    while True:
        ok, frame = cap.read()
        if not ok:
            continue

        # เซฟเฟรมดิบก่อนวาด overlay (กรอบเหลืองต้องไม่ติดไปในรูปเทรน!)
        raw = frame.copy()

        # กรอบเหลือง = ghost ที่โมเดลเห็นตอนนี้ → เฟรมแบบนี้แหละที่ควรถ่าย
        results = model.predict(frame, conf=GHOST_CONF, verbose=False)
        for box in results[0].boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            name = model.names[int(box.cls)]
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)
            cv2.putText(frame, f"ghost? {name} {float(box.conf):.0%}",
                        (x1, max(25, y1 - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

        cv2.putText(frame, f"bg saved: {count}/100  auto: {'ON' if auto else 'off'}",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.imshow("capture negatives (SPACE/a/q)", frame)
        key = cv2.waitKey(1) & 0xFF

        save = False
        if key == 32:
            save = True
        elif key == ord("a"):
            auto = not auto
        elif key == ord("q"):
            break
        if auto and time.time() - last_auto > 1.0:
            save = True
            last_auto = time.time()

        if save:
            stem = f"bg_{int(time.time() * 1000)}"
            cv2.imwrite(str(IMG_DIR / f"{stem}.jpg"), raw)
            # label เปล่า = บอก YOLO ว่ารูปนี้ "ไม่มีเป้าเลย" (background)
            (LBL_DIR / f"{stem}.txt").write_text("", encoding="utf-8")
            count += 1

    cap.release()
    cv2.destroyAllWindows()
    print(f"เสร็จ — negative รวม {count} รูป")
    print("ขั้นต่อไป: เทรนใหม่ (ดูคำสั่งใน tools/retrain.md หรือถาม Claude)")


if __name__ == "__main__":
    main()
