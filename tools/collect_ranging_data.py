# =============================================================
# collect_ranging_data.py — เก็บข้อมูลแคมเปญคาลิเบรตระยะแบบไว
# (มาแทนการจดใส่ Excel มือ — กดปุ่มเดียวบันทึกลง CSV เอง)
#
# วิธีใช้:
#   venv\Scripts\python.exe tools\collect_ranging_data.py
#
# ขั้นตอนหน้างาน:
#   1) กด d  → พิมพ์ระยะจริง (cm) ในหน้าต่างดำ (console) แล้ว Enter
#   2) กด p  → สลับชื่อท่า (ตรง/ซ้าย/ขวา/หลัง/หัว/ตูด/หงายท้อง)
#   3) วางตุ๊กตา แล้วกด SPACE → เก็บ 15 เฟรม เอา median บันทึก 1 แถว
#   4) ย้ายจุด/เปลี่ยนท่า แล้ววนข้อ 1-3 | กด q จบ
#
# ผลลัพธ์: Distance\ranging_log.csv (เขียนต่อท้ายเรื่อยๆ ไม่ทับของเก่า)
# เอาไปวิเคราะห์/fit ได้เลย — 1 แถว = 1 การวัด
# ⚠ เก็บข้อมูลชุดจริงหลังเทรนโมเดลใหม่เท่านั้น (real_size_mm ผูกกับ
#   นิสัยการตีกรอบของโมเดล — เปลี่ยนโมเดล = ข้อมูลเก่าใช้ไม่ได้)
# =============================================================
import csv
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2

from _yolo_preview import load_model

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import camera
import config

CSV_PATH = Path(__file__).resolve().parent.parent / "Distance" / "ranging_log.csv"
CSV_COLUMNS = ["เวลา", "ตัว", "ท่า", "ระยะจริง_cm", "px_w", "px_h",
               "size_px", "conf", "จำนวนเฟรม", "ความกว้างเฟรม", "โมเดล"]
POSES = ["ตรง", "ซ้าย", "ขวา", "หลัง", "หัว", "ตูด", "หงายท้อง"]
RECORD_FRAMES = 15           # เก็บกี่เฟรมต่อการกด SPACE 1 ครั้ง (เอา median)
WINDOW = "collect ranging data (d=ระยะ p=ท่า SPACE=บันทึก q=ออก)"


def best_box(model, frame):
    """กรอบที่มั่นใจสุดในเฟรม (แคมเปญวางทีละตัว จึงเอาตัวเดียวพอ)"""
    results = model.predict(frame, conf=config.YOLO_CONF, verbose=False)
    best = None
    for box in results[0].boxes:
        if best is None or float(box.conf) > float(best.conf):
            best = box
    return best


def record_point(cap, model, dist_cm, pose):
    """อ่าน RECORD_FRAMES เฟรม เก็บ median ขนาดกรอบ แล้วต่อท้าย CSV 1 แถว"""
    ws, hs, confs, label = [], [], [], None
    t0 = time.time()
    while len(ws) < RECORD_FRAMES and time.time() - t0 < 10:
        ok, frame = cap.read()
        if not ok:
            continue
        box = best_box(model, frame)
        if box is None:
            continue
        x1, y1, x2, y2 = map(float, box.xyxy[0])
        ws.append(x2 - x1)
        hs.append(y2 - y1)
        confs.append(float(box.conf))
        label = model.names[int(box.cls)]
        # โชว์ความคืบหน้าระหว่างเก็บ
        cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 200, 255), 3)
        cv2.putText(frame, f"REC {len(ws)}/{RECORD_FRAMES}", (20, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.3, (0, 200, 255), 3)
        cv2.imshow(WINDOW, frame)
        cv2.waitKey(1)

    if not ws:
        print("  ⚠ 10 วิแล้วยังไม่เจอตุ๊กตาในภาพเลย — ไม่บันทึก")
        return None

    w = statistics.median(ws)
    h = statistics.median(hs)
    row = [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), label, pose, dist_cm,
           round(w, 1), round(h, 1), round((w * h) ** 0.5, 1),
           round(statistics.median(confs), 3), len(ws),
           config.FRAME_WIDTH, Path(config.YOLO_MODEL_PATH).name]

    new_file = not CSV_PATH.exists()
    with open(CSV_PATH, "a", newline="", encoding="utf-8-sig") as f:  # sig = เปิดใน Excel ไม่เพี้ยน
        wr = csv.writer(f)
        if new_file:
            wr.writerow(CSV_COLUMNS)
        wr.writerow(row)
    return row


def main():
    print("กำลังเปิดกล้อง...")
    cap = camera.open_camera()
    model = load_model()
    dist_cm = None
    pose_i = 0
    saved = 0
    last = ""
    print(f"พร้อมแล้ว — บันทึกลง {CSV_PATH}")
    print("d = ตั้งระยะจริง | p = สลับท่า | SPACE = บันทึก | q = ออก")

    cv2.namedWindow(WINDOW)
    while True:
        if cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
            break
        ok, frame = cap.read()
        if not ok:
            cv2.waitKey(1)
            continue

        box = best_box(model, frame)
        if box is not None:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            label = model.names[int(box.cls)]
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
            cv2.putText(frame, f"{label} {float(box.conf):.0%}",
                        (x1, max(25, y1 - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

        hud = f"dist: {dist_cm if dist_cm else '-- (กด d)'} cm | pose: {POSES[pose_i]} | saved: {saved}"
        cv2.putText(frame, hud, (20, frame.shape[0] - 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)
        if last:
            cv2.putText(frame, last, (20, frame.shape[0] - 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
        cv2.imshow(WINDOW, frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key == ord("d"):
            try:
                dist_cm = float(input("ระยะจริง (cm): "))
                print(f"  ตั้งระยะ = {dist_cm:.0f} cm")
            except ValueError:
                print("  ⚠ พิมพ์เป็นตัวเลข")
        elif key == ord("p"):
            pose_i = (pose_i + 1) % len(POSES)
            print(f"  ท่า = {POSES[pose_i]}")
        elif key == ord(" "):
            if dist_cm is None:
                print("  ⚠ ยังไม่ได้ตั้งระยะ — กด d ก่อน")
                continue
            row = record_point(cap, model, dist_cm, POSES[pose_i])
            if row:
                saved += 1
                last = f"saved: {row[1]} {row[2]} @{row[3]:.0f}cm size={row[6]}px"
                print(f"  ✅ [{saved}] {last}")

    cap.release()
    cv2.destroyAllWindows()
    print(f"\nจบ — บันทึกทั้งหมด {saved} แถว → {CSV_PATH}")


if __name__ == "__main__":
    main()


