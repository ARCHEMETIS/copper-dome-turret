# =============================================================
# test_on_webcam.py — เปิดเว็บแคมจริง รันโมเดล YOLO ที่เทรนแล้วแบบสดๆ
# ไม่ต้องมี Arduino / ตุ๊กตาก็ดูได้ว่าโมเดลตรวจจับอะไรได้บ้าง
# รัน: python tools/test_on_webcam.py
# กด q เพื่อปิดหน้าต่าง
# =============================================================
import sys
from pathlib import Path

import cv2

from _yolo_preview import draw_detections, load_model

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import camera


def main():
    print("กำลังเปิดกล้อง...")
    cap = camera.open_camera()
    model = load_model()
    print("พร้อมแล้ว — กด q ที่หน้าต่างวิดีโอเพื่อปิด")

    while True:
        ok, frame = cap.read()
        if not ok:
            continue
        frame = draw_detections(frame, model)
        cv2.imshow("YOLO webcam test (q = quit)", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
