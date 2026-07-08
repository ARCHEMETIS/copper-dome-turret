# =============================================================
# test_on_video.py — รันโมเดล YOLO ที่เทรนแล้วกับไฟล์วิดีโอ (ไม่ต้องมีตุ๊กตาจริง/กล้อง)
# รัน: python tools/test_on_video.py
# กด q เพื่อปิดหน้าต่างระหว่างเล่น
# =============================================================
import sys
from pathlib import Path

import cv2
from ultralytics import YOLO

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import config

VIDEO_PATH = Path(__file__).resolve().parent.parent / "VideoForTest.mp4"
OUT_PATH = Path(__file__).resolve().parent.parent / "VideoForTest_detected.mp4"


def main():
    model = YOLO(config.YOLO_MODEL_PATH)
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
        results = model.predict(frame, conf=config.YOLO_CONF, verbose=False)
        for box in results[0].boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            label = model.names[int(box.cls)]
            conf = float(box.conf)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
            cv2.putText(frame, f"{label} {conf:.0%}", (x1, max(25, y1 - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
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
