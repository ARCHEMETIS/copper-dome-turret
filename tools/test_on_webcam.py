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


WINDOW_NAME = "YOLO webcam test (q = quit)"
MAX_CONSECUTIVE_READ_FAILS = 30  # read ที่ fail คืนค่าเร็วมาก — กล้องหลุดจริงจะครบเกณฑ์แทบทันที


def main():
    print("กำลังเปิดกล้อง...")
    cap = camera.open_camera()
    model = load_model()
    print("พร้อมแล้ว — กด q หรือกดปิดหน้าต่างเพื่อออก")

    cv2.namedWindow(WINDOW_NAME)
    consecutive_fails = 0
    while True:
        # คลิกปุ่ม X ปิดหน้าต่างแล้วโค้ดไม่รู้ตัว จะเปิดหน้าต่างใหม่ทับทันทีในลูปถัดไป
        # (มองจากคนใช้เหมือน "ปิดแล้วเปิดเองไม่หยุด") เช็คตรงนี้กันไว้
        if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
            break

        ok, frame = cap.read()
        if not ok:
            consecutive_fails += 1
            if consecutive_fails >= MAX_CONSECUTIVE_READ_FAILS:
                print("⚠️ กล้องไม่ตอบสนองต่อเนื่อง — เช็คว่าแอปอื่น (Zoom/Teams/Camo) ถือกล้องอยู่หรือเปล่า")
                break
            cv2.waitKey(1)  # ยังต้องเรียกไว้ ไม่งั้นหน้าต่างค้าง (Windows ขึ้น Not Responding)
            continue
        consecutive_fails = 0

        frame = draw_detections(frame, model)
        cv2.imshow(WINDOW_NAME, frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
