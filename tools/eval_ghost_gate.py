# =============================================================
# eval_ghost_gate.py — validate ประตูกัน ghost ใน YoloDetector (wayfinder #10)
# รัน:  venv\Scripts\python.exe tools\eval_ghost_gate.py
#
# จำลองจังหวะของ aiming loop จริง (AIM_SETTLE_S ~0.2s = ~5fps) ด้วยการ
# เดินคลิป 60fps แบบ stride 12 แล้วเรียก detector.detect ต่อ label:
#   - คลิป negative (Downloads/VID_20260710_*): detection ที่หลุดออกมา = ghost
#     ที่จะทำป้อมหันผิด/ยิงผิดจริง — เทียบ "ผ่านประตู" กับ "ไม่มีประตู"
#   - VideoForTest.mp4 (มีตุ๊กตา): วัดว่าประตูหน่วงการเจอเป้าจริงแค่ไหน
# =============================================================
import sys
from pathlib import Path

import cv2

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "src"))
import config                      # noqa: E402
from detector import YoloDetector  # noqa: E402

STRIDE = 12          # 60fps / 12 ≈ 5fps ≈ จังหวะ loop เล็งจริง (AIM_SETTLE_S 0.2s)
NEG_CLIPS = [Path.home() / "Downloads" / n for n in [
    "VID_20260710_161828.mp4", "VID_20260710_161937.mp4",
    "VID_20260710_162023.mp4", "VID_20260710_162931.mp4~2.mp4",
    "VID_20260710_163010.mp4"]]


def walk(video, det, label):
    """เดินคลิปตามจังหวะ loop คืน (เฟรมที่เช็ค, เฟรมที่ประตูปล่อย, raw sighting,
    ลำดับเฟรมแรกที่ปล่อย)"""
    cap = cv2.VideoCapture(str(video))
    det._persist.clear()
    checked = passed = raw = 0
    first_pass = None
    i = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        i += 1
        if i % STRIDE:
            continue
        checked += 1
        # raw = มีกรอบ class นี้ conf ถึงเกณฑ์ไหม (วัดเทียบ ไม่ผ่านประตู)
        want = config.TARGETS[label]["yolo_class"]
        res = det.model.predict(frame, conf=config.YOLO_CONF, verbose=False)[0]
        if any(int(b.cls) == want for b in res.boxes):
            raw += 1
        d = det.detect(frame, label)
        if d is not None:
            passed += 1
            if first_pass is None:
                first_pass = checked
    cap.release()
    return checked, passed, raw, first_pass


def main():
    det = YoloDetector()
    print(f"ประตู: persist={config.GATE_PERSIST_FRAMES}, "
          f"dist={config.GATE_DIST_RANGE_MM}mm, จังหวะ ~{60/STRIDE:.0f}fps\n")

    print("=== คลิป negative: detection ที่หลุด = ghost อันตรายจริง ===")
    total_pass = total_raw = total_checked = 0
    for clip in NEG_CLIPS:
        for label in config.TARGETS:
            checked, passed, raw, _ = walk(clip, det, label)
            total_pass += passed
            total_raw += raw
            total_checked += checked
            if raw or passed:
                print(f"  {clip.name} × {label}: raw {raw}/{checked} "
                      f"→ ผ่านประตู {passed}")
    print(f"รวมทุกคลิป×ทุก label: raw {total_raw} เฟรม "
          f"→ ผ่านประตู {total_pass} เฟรม (เช็คทั้งหมด {total_checked})\n")

    print("=== VideoForTest.mp4: ประตูหน่วงเป้าจริงแค่ไหน ===")
    for label in config.TARGETS:
        checked, passed, raw, first = walk(PROJECT / "VideoForTest.mp4", det, label)
        if raw:
            delay = "-" if first is None else f"{first}"
            print(f"  {label}: raw {raw}/{checked} → ผ่านประตู {passed} "
                  f"(ปล่อยครั้งแรกที่เฟรมเช็คลำดับ {delay})")


if __name__ == "__main__":
    main()
