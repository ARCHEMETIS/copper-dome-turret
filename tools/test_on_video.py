# =============================================================
# test_on_video.py — รันโมเดล YOLO ที่เทรนแล้วกับไฟล์วิดีโอ (ไม่ต้องมีตุ๊กตาจริง/กล้อง)
# รัน: python tools/test_on_video.py
# กด q เพื่อปิดหน้าต่างระหว่างเล่น
# =============================================================
from pathlib import Path

import cv2

from _yolo_preview import draw_detections, load_model

VIDEO_PATH = Path(__file__).resolve().parent.parent / "VideoForTest.mp4"
OUT_PATH = Path(__file__).resolve().parent.parent / "VideoForTest_detected.mp4"
WINDOW_NAME = "YOLO test (q = quit)"


def main():
    model = load_model()
    cap = cv2.VideoCapture(str(VIDEO_PATH))
    if not cap.isOpened():
        raise RuntimeError(f"เปิดวิดีโอไม่ได้: {VIDEO_PATH}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    writer = cv2.VideoWriter(str(OUT_PATH), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

    cv2.namedWindow(WINDOW_NAME)
    while True:
        # กดปุ่ม X ปิดหน้าต่างแล้วโค้ดไม่รู้ตัว จะเปิดหน้าต่างใหม่ทับทันทีในลูปถัดไป
        # (มองจากคนใช้เหมือน "ปิดแล้วเปิดเองไม่หยุด") เช็คตรงนี้กันไว้
        if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
            break

        ok, frame = cap.read()
        if not ok:
            break
        frame = draw_detections(frame, model)
        writer.write(frame)
        cv2.imshow(WINDOW_NAME, frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    writer.release()
    cv2.destroyAllWindows()
    print(f"บันทึกวิดีโอผลลัพธ์ไว้ที่: {OUT_PATH}")


if __name__ == "__main__":
    main()
