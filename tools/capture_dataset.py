# =============================================================
# capture_dataset.py — ถ่ายรูปตุ๊กตาเก็บไว้เทรน YOLO
# เป้าหมาย ~100-150 รูป/ตัว: หลายระยะ หลายมุม หลายแสง หลายฉากหลัง
# รัน: python tools/capture_dataset.py
# แล้วไปทำ label ที่ https://www.makesense.ai (ฟรี ไม่ต้องสมัคร, export เป็น YOLO format)
# =============================================================
import sys
import time
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import camera

OUT_DIR = Path(__file__).resolve().parent.parent / "dataset" / "images"


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cap = camera.open_camera()
    count = len(list(OUT_DIR.glob("*.jpg")))
    print(f"SPACE = ถ่าย 1 รูป | a = ถ่ายอัตโนมัติทุก 1 วิ (กดอีกทีหยุด) | q = ออก")
    print(f"บันทึกที่: {OUT_DIR} (มีอยู่แล้ว {count} รูป)")

    auto = False
    last_auto = 0.0
    while True:
        ok, frame = cap.read()
        if not ok:
            continue
        cv2.putText(frame, f"saved: {count}  auto: {'ON' if auto else 'off'}",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.imshow("capture (SPACE/a/q)", frame)
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
            path = OUT_DIR / f"img_{int(time.time() * 1000)}.jpg"
            cv2.imwrite(str(path), frame)
            count += 1

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
