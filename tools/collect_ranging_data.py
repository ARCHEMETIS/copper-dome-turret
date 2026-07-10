# =============================================================
# collect_ranging_data.py — เก็บข้อมูลแคมเปญคาลิเบรตระยะแบบไว
# (มาแทนการจดใส่ Excel มือ — กดปุ่มเดียวบันทึกลง CSV เอง)
#
# วิธีใช้:
#   venv\Scripts\python.exe tools\collect_ranging_data.py
#
# ขั้นตอนหน้างาน (คำสั่งทั้งหมดโชว์บนจอด้วย):
#   1) กด d → พิมพ์ระยะจริง (cm) "ในหน้าต่างกล้องเลย" แล้ว Enter
#      (Backspace ลบ, Esc ยกเลิก — ไม่ต้องสลับไป console แล้ว)
#   2) กด p → สลับชื่อท่า (ตรง/ซ้าย/ขวา/หลัง/หัว/ตูด/หงายท้อง)
#   3) วางตุ๊กตา แล้วกด SPACE → เก็บ 15 เฟรม เอา median บันทึก 1 แถว
#   4) ย้ายจุด/เปลี่ยนท่า แล้ววนข้อ 1-3 | กด q จบ
#
# บนจอมีสรุปว่าเก็บระยะไหนไปกี่แถว + ตัวไหนเก็บครบกี่ท่าที่ระยะปัจจุบัน
# (โหลดของเก่าจาก CSV ตอนเปิด — ปิดแล้วเปิดใหม่สรุปไม่หาย)
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
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from _yolo_preview import load_model

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import camera
import config

CSV_PATH = Path(__file__).resolve().parent.parent / "Distance" / "ranging_log.csv"
CSV_COLUMNS = ["เวลา", "ตัว", "ท่า", "ระยะจริง_cm", "px_w", "px_h",
               "size_px", "conf", "จำนวนเฟรม", "ความกว้างเฟรม", "โมเดล"]
POSES = ["ตรง", "ซ้าย", "ขวา", "หลัง", "หัว", "ตูด", "หงายท้อง"]
RECORD_FRAMES = 15           # เก็บกี่เฟรมต่อการกด SPACE 1 ครั้ง (เอา median)
WINDOW = "collect ranging data"

# cv2.putText วาดภาษาไทยไม่ได้ (ฟอนต์ Hershey มีแต่ ASCII — ขึ้นเป็น ????)
# เลยวาดข้อความผ่าน Pillow ด้วยฟอนต์ระบบ Windows แทน
_FONT_PATH = "C:/Windows/Fonts/LeelawUI.ttf"
_font_cache: dict[int, ImageFont.FreeTypeFont] = {}


def _font(size: int) -> ImageFont.FreeTypeFont:
    if size not in _font_cache:
        _font_cache[size] = ImageFont.truetype(_FONT_PATH, size)
    return _font_cache[size]


def draw_hud(frame, lines):
    """วาดข้อความไทยหลายบรรทัดมุมล่างซ้าย (พื้นดำโปร่งให้อ่านออกทุกฉากหลัง)
    lines = [(ข้อความ, สี RGB), ...] เรียงบนลงล่าง"""
    if not lines:
        return frame
    size = 22
    pad = 8
    line_h = size + 8
    box_h = pad * 2 + line_h * len(lines)
    h = frame.shape[0]

    overlay = frame.copy()
    cv2.rectangle(overlay, (0, h - box_h), (frame.shape[1], h), (0, 0, 0), -1)
    frame = cv2.addWeighted(overlay, 0.55, frame, 0.45, 0)

    pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    d = ImageDraw.Draw(pil)
    y = h - box_h + pad
    for text, color in lines:
        d.text((12, y), text, font=_font(size), fill=color)
        y += line_h
    return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)


def load_collected():
    """อ่าน CSV เดิม (ถ้ามี) → dict: ระยะ_cm -> set ของ (ตัว, ท่า) ที่เก็บแล้ว
    ไว้โชว์สรุปบนจอ — นับเฉพาะแถวของโมเดลปัจจุบัน (ข้อมูลข้ามโมเดลใช้ไม่ได้)"""
    collected = defaultdict(set)
    model_name = Path(config.YOLO_MODEL_PATH).name
    if not CSV_PATH.exists():
        return collected
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row.get("โมเดล") != model_name:
                continue
            try:
                dist = float(row["ระยะจริง_cm"])
            except (ValueError, KeyError):
                continue
            collected[dist].add((row["ตัว"], row["ท่า"]))
    return collected


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
    frame_w = None               # ความกว้างเฟรม "จริง" ที่วัด px มา — ห้ามใช้ค่า
    t0 = time.time()             # จาก config เพราะกล้องอาจส่งขนาดอื่นมาโดยไม่บอก
    while len(ws) < RECORD_FRAMES and time.time() - t0 < 10:
        ok, frame = cap.read()
        if not ok:
            continue
        frame_w = frame.shape[1]
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
           frame_w, Path(config.YOLO_MODEL_PATH).name]

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
    collected = load_collected()   # ระยะ_cm -> {(ตัว, ท่า), ...} จาก CSV เดิม
    dist_cm = None
    pose_i = 0
    saved = 0
    last = ""
    typing = False               # True = กำลังพิมพ์ระยะในหน้าต่างกล้อง
    type_buf = ""
    print(f"พร้อมแล้ว — บันทึกลง {CSV_PATH}")
    print("คำสั่งทั้งหมดโชว์อยู่บนหน้าต่างกล้อง")

    cv2.namedWindow(WINDOW)
    while True:
        if cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
            break
        ok, frame = cap.read()
        if not ok:
            cv2.waitKey(1)
            continue

        box = best_box(model, frame)
        label_now = None
        if box is not None:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            label_now = model.names[int(box.cls)]
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
            cv2.putText(frame, f"{label_now} {float(box.conf):.0%}",
                        (x1, max(25, y1 - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

        # ---------- HUD ----------
        WHITE, YELLOW, CYAN, GRAY, ORANGE = ((255,) * 3, (255, 235, 60),
                                             (80, 220, 255), (185, 185, 185),
                                             (255, 170, 60))
        lines = [("d=พิมพ์ระยะ | p=สลับท่า | SPACE=บันทึก | q=ออก", GRAY)]

        if typing:
            lines.append((f"ระยะจริง: {type_buf}_ cm   (Enter=ตกลง  Esc=ยกเลิก  Backspace=ลบ)", YELLOW))
        else:
            dist_txt = f"{dist_cm:g} cm" if dist_cm is not None else "-- (กด d)"
            lines.append((f"ระยะ: {dist_txt}   ท่า: {POSES[pose_i]}   บันทึกรอบนี้: {saved}", WHITE))

        # สรุปว่าเก็บระยะไหนไปแล้วกี่แถว (รวมของเก่าใน CSV โมเดลเดียวกัน)
        if collected:
            summary = "  ".join(f"{d:g}cm×{len(v)}" for d, v in sorted(collected.items()))
            lines.append((f"เก็บแล้ว: {summary}", CYAN))

        # ที่ระยะปัจจุบัน ตัวไหนได้กี่ท่าจาก 7 — เห็นเลยว่าเหลืออะไร
        if dist_cm is not None:
            done = collected.get(dist_cm, set())
            per_toy = "   ".join(
                f"{toy} {sum(1 for t, _ in done if t == toy)}/{len(POSES)}"
                for toy in ("dino", "capybara", "elephant"))
            lines.append((f"@{dist_cm:g}cm: {per_toy}", CYAN))
            # เตือนถ้าตัวที่เห็นอยู่ + ท่าปัจจุบัน เก็บไปแล้ว (กันเก็บซ้ำโดยไม่ตั้งใจ)
            if label_now and (label_now, POSES[pose_i]) in done:
                lines.append((f"[ซ้ำ] {label_now} ท่า{POSES[pose_i]} @{dist_cm:g}cm เก็บแล้ว — เปลี่ยนท่า (p) หรือเก็บซ้ำก็ได้", ORANGE))

        if last:
            lines.append((last, GRAY))
        frame = draw_hud(frame, lines)
        cv2.imshow(WINDOW, frame)

        key = cv2.waitKey(1) & 0xFF

        # ---------- โหมดพิมพ์ระยะ (พิมพ์ในหน้าต่างกล้อง ไม่ใช้ console — ไม่ค้าง) ----------
        if typing:
            if key in (13, 10):                       # Enter = ตกลง
                try:
                    dist_cm = float(type_buf)
                    print(f"  ตั้งระยะ = {dist_cm:g} cm")
                except ValueError:
                    print("  ⚠ ตัวเลขไม่ถูกต้อง — ยังไม่ตั้งระยะ")
                typing = False
            elif key == 27:                           # Esc = ยกเลิก
                typing = False
            elif key in (8, 127):                     # Backspace = ลบ
                type_buf = type_buf[:-1]
            elif ord("0") <= key <= ord("9") or key == ord("."):
                type_buf += chr(key)
            continue

        if key == ord("q"):
            break
        elif key == ord("d"):
            typing = True
            type_buf = ""
        elif key == ord("p"):
            pose_i = (pose_i + 1) % len(POSES)
        elif key == ord(" "):
            if dist_cm is None:
                last = "! ยังไม่ได้ตั้งระยะ — กด d ก่อน"
                continue
            row = record_point(cap, model, dist_cm, POSES[pose_i])
            if row:
                saved += 1
                collected[dist_cm].add((row[1], row[2]))
                last = f"บันทึกแล้ว: {row[1]} {row[2]} @{row[3]:g}cm size={row[6]}px"
                print(f"  [{saved}] {last}")

    cap.release()
    cv2.destroyAllWindows()
    print(f"\nจบ — บันทึกทั้งหมด {saved} แถว → {CSV_PATH}")


if __name__ == "__main__":
    main()
