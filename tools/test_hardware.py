# =============================================================
# test_hardware.py — ทดสอบฮาร์ดแวร์ทีละส่วน "รันไฟล์นี้เป็นไฟล์แรก"
# ก่อน vision/UI ต้องพิสูจน์ก่อนว่า: servo หมุนได้, ล้อหมุนได้, feeder ดันได้
# รัน: python tools/test_hardware.py
# =============================================================
import msvcrt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import config
import hardware

HELP = """
กดปุ่มเดียวสั่งได้เลย ไม่ต้อง Enter:
  a / d        หมุนป้อมซ้าย / ขวา ทีละ 5°
  A / D        หมุนป้อมซ้าย / ขวา ทีละ 20°
  c            กลับ center
  0-9          ตั้งความเร็วล้อ (0=หยุด, 9=90%)
  f            feeder ดัน 1 ครั้ง
  t            ยิงจริง 1 นัด (spin-up → feed → stop) ที่ duty ล่าสุด
  q            ออก
"""

def main():
    print("กำลังต่อ Arduino ...")
    turret = hardware.Turret()
    print("ต่อสำเร็จ!", HELP)
    duty = 0.5
    try:
        while True:
            print(f"\r[pan={turret.pan_angle:.0f}° duty={duty:.1f}] > ", end="", flush=True)
            cmd = msvcrt.getwch()  # อ่านทีละปุ่ม ไม่ต้องรอ Enter
            if cmd.lower() == "q":
                print()
                break
            elif cmd == "a":
                turret.pan_by(-5)
            elif cmd == "d":
                turret.pan_by(+5)
            elif cmd == "A":
                turret.pan_by(-20)
            elif cmd == "D":
                turret.pan_by(+20)
            elif cmd == "c":
                turret.pan_to(config.PAN_CENTER)
            elif cmd == "f":
                turret.feed_one()
            elif cmd == "t":
                print(f"\nยิงที่ duty {duty} ...")
                turret.fire(duty)
            elif cmd.isdigit():
                duty = int(cmd) / 10
                turret.set_flywheel(duty)
                print(f"\nล้อหมุนที่ {duty * 100:.0f}%")
            elif cmd in ("\r", "\n"):
                pass  # เผลอกด Enter = เฉยๆ ไม่ต้องโชว์ help
            else:
                print(HELP)
    finally:
        turret.close()
        print("ปิดบอร์ดเรียบร้อย")


if __name__ == "__main__":
    main()
