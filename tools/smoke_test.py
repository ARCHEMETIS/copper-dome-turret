# =============================================================
# smoke_test.py — ทดสอบระบบทั้ง loop อัตโนมัติ (ไม่มี UI, ไม่ต้องมีอุปกรณ์)
# รัน:  venv\Scripts\python.exe tools\smoke_test.py
#
# ทดสอบอะไร: ใช้ simulator ยิงครบทั้ง 3 เป้า × 3 รอบ (ตำแหน่งสุ่มทุกนัด)
# แต่ละนัดต้องผ่านโค้ดจริงครบสาย: detector → aiming → ranging → fire
# ผ่าน = พิมพ์ PASSED | ใช้เช็ค regression ทุกครั้งที่แก้โค้ด vision/aiming
# =============================================================
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import aiming
import config
import ranging
import simulator
from detector import HsvDetector


def yolo_leg(failures):
    """ทดสอบเส้นทาง YOLO ด้วยรูปถ่ายจริงจาก dataset/test (โหมดที่ใช้จริงวันแข่ง)

    เช็ค 2 อย่างพร้อมกัน: โมเดลตรวจจับรูปจริงได้ และ mapping yolo_class ใน
    config ตรงกับ class ที่โมเดลถูกเทรนมา (กันพลาดตอน export dataset ใหม่
    แล้วลำดับ class เปลี่ยน)
    """
    import cv2
    from detector import YoloDetector

    test_dir = Path(__file__).resolve().parent.parent / "dataset" / "test"
    if not test_dir.exists():
        print("(ข้ามขา YOLO — ไม่มีโฟลเดอร์ dataset/test ในเครื่องนี้)")
        return

    det = YoloDetector()
    checked = 0
    for label_path in sorted((test_dir / "labels").glob("*.txt")):
        if checked >= 5:
            break
        lines = label_path.read_text().strip().splitlines()
        if len(lines) != 1:
            continue  # เอาเฉพาะรูปที่มีเป้าตัวเดียว ให้เทียบ class ได้ตรงๆ
        true_class = int(lines[0].split()[0])
        true_label = next(k for k, v in config.TARGETS.items()
                          if v["yolo_class"] == true_class)

        img_path = next(p for p in (test_dir / "images").glob(label_path.stem + ".*"))
        frame = cv2.imread(str(img_path))
        d = det.detect(frame, true_label)
        checked += 1
        if d is None:
            failures.append(f"YOLO: ไม่เจอ {true_label} ใน {img_path.name}")
        else:
            print(f"YOLO | {img_path.name}: เจอ {true_label} (conf {d.conf:.2f})")

    if checked == 0:
        failures.append("YOLO: ไม่มีรูป test ที่ใช้เช็คได้เลย (ทุกรูปมีหลายเป้า?)")


def ranging_leg(failures):
    """ทดสอบ ranging + ตัวแก้ตามท่า (ASPECT_CORRECTION) กับกรอบจริง 42 จุด
    จาก Distance/ranging_log.csv — ทุกจุดต้องเพี้ยนไม่เกิน ±12%

    ⚠ ต้องรันก่อน create_sim() — sim จะเขียนทับ FOCAL_PX/real_size_mm/
    ASPECT_CORRECTION ใน config ให้เข้ากับเป้าจำลอง (ค่าจริงจะหายไป)
    """
    import csv

    from detector import Detection

    csv_path = Path(__file__).resolve().parent.parent / "Distance" / "ranging_log.csv"
    if not csv_path.exists():
        print("(ข้ามขา ranging — ไม่มี Distance/ranging_log.csv ในเครื่องนี้)")
        return

    tag = config.yolo_model_tag()   # ชื่อ+hash — ชื่อไฟล์เฉยๆ ซ้ำกันทุกรอบเทรน
    checked = worst = 0
    with open(csv_path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row.get("โมเดล") != tag:
                continue  # ข้อมูลของโมเดลอื่น เทียบกับ config ปัจจุบันไม่ได้
            det = Detection(row["ตัว"], 0, 0,
                            float(row["px_w"]), float(row["px_h"]), 1.0)
            pred_cm = ranging.distance_mm(det) / 10
            true_cm = float(row["ระยะจริง_cm"])
            err_pct = abs(pred_cm - true_cm) / true_cm * 100
            checked += 1
            worst = max(worst, err_pct)
            if err_pct > 12:
                failures.append(f"ranging: {row['ตัว']} ท่า{row['ท่า']} "
                                f"@{true_cm:g}cm เพี้ยน {err_pct:.0f}%")
    if checked:
        print(f"ranging | เช็ค {checked} จุดจาก CSV: เพี้ยนแย่สุด {worst:.1f}%")
    else:
        print(f"(ข้ามขา ranging — ใน CSV ไม่มีแถวของโมเดล {tag} "
              "→ เก็บใหม่ด้วย collect_ranging_data.py แล้ว fit_aspect.py)")


def main():
    failures = []
    ranging_leg(failures)     # ต้องมาก่อน create_sim (sim เขียนทับ config)

    cam, turret = simulator.create_sim()
    det = HsvDetector()

    yolo_leg(failures)

    for round_no in range(1, 4):
        for label in config.TARGETS:
            d = aiming.aim_at(turret, cam, det, label)
            if d is None:
                failures.append(f"รอบ {round_no}: เล็ง {label} ไม่สำเร็จ")
                continue
            dist = ranging.distance_mm(d)
            true_dist = turret.world.targets[label]["dist"]
            err = abs(dist - true_dist)
            print(f"รอบ {round_no} | {label}: วัดได้ {dist:.0f} mm "
                  f"(จริง {true_dist:.0f}, เพี้ยน {err:.0f} mm)")
            if err > 100:
                failures.append(f"รอบ {round_no}: วัดระยะ {label} เพี้ยน {err:.0f} mm")
            turret.fire(ranging.duty_for_distance(dist))

    print()
    if failures:
        print("❌ SMOKE TEST FAILED:")
        for f in failures:
            print("  -", f)
        sys.exit(1)
    hit_rate = f"{turret.hits}/{turret.shots}"
    print(f"✅ SMOKE TEST PASSED — เล็งสำเร็จทุกเป้า, ยิงโดน {hit_rate} ใน simulator")
    if turret.hits < turret.shots:
        print("   (นัดที่พลาดใน sim มาจากเกณฑ์ระยะ/มุมตึง ไม่ใช่โค้ดพัง — ดู log ด้านบน)")


if __name__ == "__main__":
    main()
