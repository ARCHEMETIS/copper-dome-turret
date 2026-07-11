# =============================================================
# fit_aspect.py — fit ตัวแก้ระยะตามท่า (config.ASPECT_CORRECTION)
# จาก Distance/ranging_log.csv (เก็บด้วย tools/collect_ranging_data.py)
# รัน:  venv\Scripts\python.exe tools\fit_aspect.py
#
# วิธี fit: เรียงจุดตาม aspect (w/h) แล้วตัดเป็น cluster ตรงช่องว่าง
# ที่กว้างเกิน GAP → ได้ knot ละ cluster:
#   aspect = median w/h ของ cluster, factor = 1/(1+median error)
# cluster ที่กว้าง (หลายท่า aspect เกยกัน error ไล่ระดับข้างใน) แตกเป็น
# 2 knot ครึ่งล่าง/ครึ่งบน — knot เดียวเฉลี่ยทับ trend แล้วปลายๆ cluster เพี้ยน
# จัดกลุ่มตาม aspect ไม่ใช่ตามท่า — ตอนใช้งานจริง ranging รู้แค่ aspect
# (ท่าที่ aspect ชนกัน เช่น dino หัว/ตูด ยังไงก็แยกไม่ได้ ต้องยอมรับ error
# ตรงนั้น) — ranging.distance_mm ใช้ np.interp ระหว่าง knot จึงต่อเนื่อง
# ไม่มีหน้าผาแบบแถบ w/h ที่กรอบสั่นนิดเดียวแล้วระยะกระโดด 20%
#
# ใช้เฉพาะแถวของโมเดลปัจจุบัน (คอลัมน์ โมเดล ต้องตรง config.yolo_model_tag())
# ⚠ fit real_size_mm ให้เสร็จก่อน — factor ต่อยอดจากค่านั้น
# ⚠ ตัวเลข "หลังแก้" เป็น in-sample (วัดบนข้อมูลชุดเดียวกับที่ fit)
#   เช็คของจริงที่ระยะที่ไม่ได้ใช้ fit อีกชั้นก่อนเชื่อสนิท
# =============================================================
import csv
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import config

CSV_PATH = Path(__file__).resolve().parent.parent / "Distance" / "ranging_log.csv"
GAP = 0.05           # ช่องว่าง aspect กว้างเกินนี้ = ขึ้น cluster ใหม่
SPLIT_SPAN = 0.06    # cluster กว้างเกินนี้ (และมี ≥4 จุด) = แตกเป็น 2 knot


def load_points():
    """แถวของโมเดลปัจจุบัน → [(toy, pose, aspect, err)] โดย err = (วัด-จริง)/จริง"""
    tag = config.yolo_model_tag()
    points = []
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row.get("โมเดล") != tag:
                continue
            w, h = float(row["px_w"]), float(row["px_h"])
            true_mm = float(row["ระยะจริง_cm"]) * 10
            real = config.TARGETS[row["ตัว"]]["real_size_mm"]
            pred_mm = config.FOCAL_PX * real / (w * h) ** 0.5
            points.append((row["ตัว"], row["ท่า"], w / h,
                           (pred_mm - true_mm) / true_mm))
    return points


def fit_knots(points):
    """คืน {toy: [(aspect, factor), ...]} เรียงตาม aspect"""
    per_toy = defaultdict(list)                   # toy -> [(aspect, err)]
    for toy, _, aspect, err in points:
        per_toy[toy].append((aspect, err))

    def knot(c):
        return (round(statistics.median(a for a, _ in c), 3),
                round(1 / (1 + statistics.median(e for _, e in c)), 3))

    knots = {}
    for toy, pts in per_toy.items():
        pts.sort()
        clusters = [[pts[0]]]
        for a, e in pts[1:]:
            if a - clusters[-1][-1][0] > GAP:
                clusters.append([])
            clusters[-1].append((a, e))
        knots[toy] = []
        for c in clusters:
            if len(c) >= 4 and c[-1][0] - c[0][0] > SPLIT_SPAN:
                knots[toy] += [knot(c[:len(c) // 2]), knot(c[len(c) // 2:])]
            else:
                knots[toy].append(knot(c))
    return knots


def main():
    if not CSV_PATH.exists():
        sys.exit(f"ไม่มี {CSV_PATH} — เก็บข้อมูลด้วย tools/collect_ranging_data.py ก่อน")
    points = load_points()
    if not points:
        sys.exit(f"ใน CSV ไม่มีแถวของโมเดล {config.yolo_model_tag()} — "
                 "เก็บข้อมูลใหม่ด้วย tools/collect_ranging_data.py ก่อน")

    knots = fit_knots(points)

    print(f"fit จาก {len(points)} จุด ของโมเดล {config.yolo_model_tag()}\n")
    print("วางบล็อกนี้ทับใน src/config.py:\n")
    print("ASPECT_CORRECTION = {")
    for toy in sorted(knots):
        print(f'    "{toy}": {knots[toy]},')
    print("}\n")

    print(f"{'ตัว':<10}{'ท่า':<10}{'aspect':>8}{'ก่อน':>9}{'หลัง':>9}")
    worst_before = worst_after = 0.0
    for toy, pose, aspect, err in sorted(points):
        xs = [a for a, _ in knots[toy]]
        fs = [f for _, f in knots[toy]]
        after = (1 + err) * float(np.interp(aspect, xs, fs)) - 1
        worst_before = max(worst_before, abs(err))
        worst_after = max(worst_after, abs(after))
        flag = "  ⚠" if abs(after) > 0.10 else ""
        print(f"{toy:<10}{pose:<10}{aspect:>8.3f}{err:>+8.1%}{after:>+8.1%}{flag}")
    print(f"\nแย่สุด: ก่อนแก้ ±{worst_before:.1%} → หลังแก้ ±{worst_after:.1%} (in-sample)")


if __name__ == "__main__":
    main()
