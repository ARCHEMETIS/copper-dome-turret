# =============================================================
# smoke_test.py — ทดสอบระบบทั้ง loop อัตโนมัติ (ไม่มี UI, ไม่ต้องมีอุปกรณ์)
# รัน:  venv\Scripts\python.exe tools\smoke_test.py
#
# ทดสอบอะไร: ใช้ simulator ยิงครบทั้ง 3 เป้า × 3 รอบ (ตำแหน่งสุ่มทุกนัด)
# แต่ละนัดต้องผ่านโค้ดจริงครบสาย: detector → aiming → ranging → fire
# ผ่าน = พิมพ์ PASSED | ใช้เช็ค regression ทุกครั้งที่แก้โค้ด vision/aiming
# =============================================================
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import aiming
import config
import ranging
import simulator
from detector import HsvDetector


def _normalise_model_names(names):
    """แปลง model.names ทั้งแบบ dict และ list ให้เทียบกับ config ได้ตรงๆ"""
    if isinstance(names, dict):
        return {int(class_id): str(label).strip().lower()
                for class_id, label in names.items()}
    return {class_id: str(label).strip().lower() for class_id, label in enumerate(names)}


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
        failures.append(
            "ล้มเหลว [ตรวจ fixture YOLO]: ไม่มีโฟลเดอร์ dataset/test "
            "จึงยืนยันครบทุก class ไม่ได้"
        )
        return

    det = YoloDetector()
    model_names = _normalise_model_names(det.model.names)
    config_names = {int(t["yolo_class"]): key for key, t in config.TARGETS.items()}
    if config_names != model_names:
        failures.append(
            "ล้มเหลว [ตรวจ mapping YOLO]: config.TARGETS ให้ mapping "
            f"{config_names} แต่ model.names รายงาน {model_names}"
        )

    fixtures_by_target = {target: [] for target in config.TARGETS}
    for label_path in sorted((test_dir / "labels").glob("*.txt")):
        lines = label_path.read_text(encoding="utf-8").strip().splitlines()
        if len(lines) != 1:
            continue  # เอาเฉพาะรูปที่มีเป้าตัวเดียว ให้เทียบ class ได้ตรงๆ
        parts = lines[0].split()
        if len(parts) < 5:
            continue
        true_class = int(parts[0])
        true_label = model_names.get(true_class)
        if true_label not in fixtures_by_target:
            continue

        image_paths = sorted((test_dir / "images").glob(label_path.stem + ".*"))
        if not image_paths:
            continue
        img_path = image_paths[0]
        frame = cv2.imread(str(img_path))
        if frame is None:
            continue

        # ข้ามรูปที่เป้ากินเฟรมใหญ่/เล็กเกินช่วงระยะใช้งานจริง (GATE_DIST_RANGE_MM)
        # ประตูขนาดใน detector จะตีตกรูปพวกนี้ "อย่างถูกต้อง" — เอามาเป็นข้อสอบไม่ได้
        # จำเป็นตั้งแต่ 20 ก.ค. 2026: dataset ถูก resplit ใหม่ ทำให้ 5 รูปแรกกลายเป็น
        # ภาพระยะประชิดจากชุดของเพื่อน (ตุ๊กตากินเฟรม 28-51% = ระยะโดยนัย ~230-300mm)
        _, _, bw_n, bh_n = (float(v) for v in parts[1:5])
        fh, fw = frame.shape[:2]
        if not det._size_plausible(true_label, bw_n * fw, bh_n * fh, fw):
            continue
        fixtures_by_target[true_label].append((img_path, frame, true_class))

    for target, fixtures in fixtures_by_target.items():
        if not fixtures:
            failures.append(
                f"ล้มเหลว [ตรวจ coverage YOLO]: ไม่มี fixture เดี่ยวที่ผ่าน size gate สำหรับ {target}"
            )

    # เลือกอย่างน้อยหนึ่งรูปต่อ class ก่อนเติมรูปเพิ่มให้ครบห้ารูป — กันลำดับชื่อไฟล์กิน dino ทิ้ง
    selected = [fixtures[0] for fixtures in fixtures_by_target.values() if fixtures]
    for offset in range(1, 5):
        for fixtures in fixtures_by_target.values():
            if len(selected) >= 5:
                break
            if len(fixtures) > offset:
                selected.append(fixtures[offset])
        if len(selected) >= 5:
            break

    checked = 0
    for img_path, frame, true_class in selected:
        true_label = model_names[true_class]
        # ประตู persistence ต้องเห็นเป้าสะสมหลายเฟรมก่อนปล่อย — รูปนิ่ง = เป้า
        # อยู่ทนอยู่แล้ว จึงป้อนรูปเดิมซ้ำเท่าเกณฑ์ (เหมือนกล้องจ้องเป้านิ่งๆ)
        for _ in range(config.GATE_PERSIST_FRAMES):
            d = det.detect(frame, true_label)
        det._persist.clear()   # กันเป้าถัดไปได้อานิสงส์ตัวนับของรูปก่อน
        checked += 1
        if d is None:
            failures.append(
                f"ล้มเหลว [ตรวจ detection YOLO]: ควรเจอ {true_label} "
                f"(class {true_class}) ใน {img_path.name} แต่ detector คืน None"
            )
        else:
            print(f"YOLO | {img_path.name}: เจอ {true_label} (conf {d.conf:.2f})")

    if checked == 0:
        failures.append("ล้มเหลว [ตรวจ fixture YOLO]: ไม่มีรูป test ที่ผ่านเกณฑ์ให้เช็คเลย")


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
    yolo_leg(failures)        # ต้องมาก่อน create_sim เช่นกัน (YOLO ใช้ calibration จริง)

    # create_sim เขียนทับ calibration จริง — snapshot ไว้เพื่อไม่ให้ smoke test เปลี่ยน process state ถาวร
    saved_focal = config.FOCAL_PX
    saved_real_sizes = {label: target["real_size_mm"]
                        for label, target in config.TARGETS.items()}
    saved_aspect = copy.deepcopy(config.ASPECT_CORRECTION)
    try:
        cam, turret = simulator.create_sim()
        det = HsvDetector()

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
                turret.fire()

        if turret.hits < turret.shots:
            failures.append(
                "ล้มเหลว [ตรวจ hit simulator]: hits < shots "
                f"({turret.hits} < {turret.shots}) — ทุกนัดที่จำลองต้องยิงโดน "
                "จึงห้ามรายงาน PASSED เมื่อมี miss"
            )
    finally:
        config.FOCAL_PX = saved_focal
        for label, real_size in saved_real_sizes.items():
            config.TARGETS[label]["real_size_mm"] = real_size
        config.ASPECT_CORRECTION = saved_aspect

    print()
    if failures:
        print("❌ SMOKE TEST FAILED:")
        for f in failures:
            print("  -", f)
        sys.exit(1)
    hit_rate = f"{turret.hits}/{turret.shots}"
    print(f"✅ SMOKE TEST PASSED — เล็งสำเร็จทุกเป้า, ยิงโดน {hit_rate} ใน simulator")


if __name__ == "__main__":
    main()
