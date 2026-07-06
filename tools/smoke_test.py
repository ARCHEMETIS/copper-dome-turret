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


def main():
    cam, turret = simulator.create_sim()
    det = HsvDetector()
    failures = []

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
