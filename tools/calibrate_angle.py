# =============================================================
# calibrate_angle.py — ทำตารางมุมเงย ↔ ระยะตกของลูก (หัวใจของคะแนนยิงแม่น)
#
# วิธี: ตั้งป้อมนิ่งๆ → ยิงที่มุมเงยต่างๆ (เช่น 20, 30, 40, 50, 60)
#       มุมละ 3-5 นัด → วัดระยะตกจริงด้วยตลับเมตร → พิมพ์ค่าเฉลี่ยลงไป
# จบแล้วสคริปต์จะพิมพ์ตารางให้ copy ไปวางใน config.TILT_ANGLE_TABLE
# รัน: python tools/calibrate_angle.py
# =============================================================
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import hardware


def main():
    turret = hardware.Turret()
    results = []  # (dist_mm, angle_deg)
    print("พิมพ์มุมเงย (องศา, เช่น 20-60) เพื่อยิง 1 นัด | 'done' เพื่อสรุปตาราง | 'q' ออกเฉยๆ")
    try:
        while True:
            cmd = input("tilt° > ").strip().lower()
            if cmd == "q":
                break
            if cmd == "done":
                results.sort()
                print("\n# copy ไปวางใน config.py แทนของเดิม:")
                print("TILT_ANGLE_TABLE = [")
                for d, a in results:
                    print(f"    ({d:.0f}, {a:.0f}),")
                print("]")
                break
            try:
                angle = float(cmd)
            except ValueError:
                continue
            input("พร้อมยิงแล้วกด Enter (ระวังอย่ายืนหน้าปืน!) ")
            turret.fire(angle)
            dist = input("ลูกตกที่ระยะกี่ mm? (เว้นว่าง = ไม่บันทึก/ยิงพลาด): ").strip()
            if dist:
                results.append((float(dist), angle))
                print(f"บันทึก: {dist} mm @ tilt {angle:.0f}°")
    finally:
        turret.close()


if __name__ == "__main__":
    main()
