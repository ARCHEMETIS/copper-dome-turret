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


def main():
    model = load_model()
    cap = cv2.VideoCapture(str(VIDEO_PATH))
    if not cap.isOpened():
        raise RuntimeError(f"เปิดวิดีโอไม่ได้: {VIDEO_PATH}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    writer = cv2.VideoWriter(str(OUT_PATH), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame = draw_detections(frame, model)
        writer.write(frame)
        cv2.imshow("YOLO test (q = quit)", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    writer.release()
    cv2.destroyAllWindows()
    print(f"บันทึกวิดีโอผลลัพธ์ไว้ที่: {OUT_PATH}")


if __name__ == "__main__":
    main()
