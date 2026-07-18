# =============================================================
# test_hardware.py — ทดสอบฮาร์ดแวร์ทีละส่วน "รันไฟล์นี้เป็นไฟล์แรก"
# ก่อน vision/UI ต้องพิสูจน์ก่อนว่า: pan/tilt servo หมุนได้, มอเตอร์ดึงสายทำงาน,
# cam_switch จับจังหวะได้, ยิงลูกออก (= 5 คะแนนแรกของเกณฑ์)
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
  w / s        มุมเงยขึ้น / ลง ทีละ 5°
  c            กลับ center (pan + tilt)
  t            ยิง 1 นัด (ดึง+ปล่อย — โหมดสโคปยิงแรงคงที่ มุมเงยตามที่ตั้งด้วย w/s)
  x            อ่านสถานะ cam_switch ตอนนี้ (True=ไม่สัมผัส, False=สัมผัส/พร้อมยิง)
  q            ออก
"""

def main():
    print("กำลังต่อ Arduino ...")
    turret = hardware.Turret()
    print("ต่อสำเร็จ!", HELP)
    try:
        while True:
            print(f"\r[pan={turret.pan_angle:.0f}° tilt={turret.tilt_angle:.0f}°] > ",
                  end="", flush=True)
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
            elif cmd == "w":
                turret.tilt_by(+5)
            elif cmd == "s":
                turret.tilt_by(-5)
            elif cmd == "c":
                turret.pan_to(config.PAN_CENTER)
                turret.tilt_to(config.TILT_CENTER)
            elif cmd == "t":
                print(f"\nยิง 1 นัด (มุมเงย {turret.tilt_angle:.0f}°) ...")
                turret.fire()
            elif cmd == "x":
                print(f"\ncam_switch = {turret.cam_switch.value}")
            elif cmd in ("\r", "\n"):
                pass  # เผลอกด Enter = เฉยๆ ไม่ต้องโชว์ help
            else:
                print(HELP)
    finally:
        turret.close()
        print("ปิดบอร์ดเรียบร้อย")


if __name__ == "__main__":
    main()
