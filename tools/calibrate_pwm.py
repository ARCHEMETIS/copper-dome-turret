# =============================================================
# calibrate_pwm.py — ทำตาราง duty ↔ ระยะตกของลูก (หัวใจของคะแนนยิงแม่น)
#
# วิธี: ตั้งป้อมนิ่งๆ → ยิงที่ duty ต่างๆ (เช่น 0.4, 0.5, ..., 1.0)
#       duty ละ 3-5 นัด → วัดระยะตกจริงด้วยตลับเมตร → พิมพ์ค่าเฉลี่ยลงไป
# จบแล้วสคริปต์จะพิมพ์ตารางให้ copy ไปวางใน config.PWM_DISTANCE_TABLE
# รัน: python tools/calibrate_pwm.py
# =============================================================
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import hardware


def main():
    turret = hardware.Turret()
    results = []  # (dist_mm, duty)
    print("พิมพ์ duty (0.35-1.0) เพื่อยิง 1 นัด | 'done' เพื่อสรุปตาราง | 'q' ออกเฉยๆ")
    try:
        while True:
            cmd = input("duty > ").strip().lower()
            if cmd == "q":
                break
            if cmd == "done":
                results.sort()
                print("\n# copy ไปวางใน config.py แทนของเดิม:")
                print("PWM_DISTANCE_TABLE = [")
                for d, p in results:
                    print(f"    ({d:.0f}, {p:.2f}),")
                print("]")
                break
            try:
                duty = float(cmd)
            except ValueError:
                continue
            input("พร้อมยิงแล้วกด Enter (ระวังอย่ายืนหน้าปืน!) ")
            turret.fire(duty)
            dist = input("ลูกตกที่ระยะกี่ mm? (เว้นว่าง = ไม่บันทึก/ยิงพลาด): ").strip()
            if dist:
                results.append((float(dist), duty))
                print(f"บันทึก: {dist} mm @ duty {duty}")
    finally:
        turret.close()


if __name__ == "__main__":
    main()
