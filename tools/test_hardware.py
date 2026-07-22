# =============================================================
# test_hardware.py — ทดสอบฮาร์ดแวร์ทีละส่วน "รันไฟล์นี้เป็นไฟล์แรก"
# ก่อน vision/UI ต้องพิสูจน์ก่อนว่า: pan/tilt servo หมุนได้, มอเตอร์ยิงทำงาน,
# ยิงลูกออกจริง (= 5 คะแนนแรกของเกณฑ์)
#
# ปุ่มที่มีให้กดเปลี่ยนตาม config.LAUNCHER — โหมด flywheel มีปุ่มหมุนล้อค้างไว้
# (ไว้เช็คทิศทางล้อ/ความเร็วโดยไม่ต้องเสียลูก) ส่วนโหมด crossbow มีปุ่มอ่าน cam_switch
# รัน: python tools/test_hardware.py
# =============================================================
import msvcrt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import config
import hardware

COMMON_HELP = """
กดปุ่มเดียวสั่งได้เลย ไม่ต้อง Enter:
  a / d        หมุนป้อมซ้าย / ขวา ทีละ 5°
  A / D        หมุนป้อมซ้าย / ขวา ทีละ 20°
  w / s        มุมเงยขึ้น / ลง ทีละ 5°
  c            กลับ center (pan + tilt)
  t            ยิง 1 นัด (โหมดสโคปยิงแรงคงที่ — เล็งด้วย pan/tilt ไม่ใช่ความแรง)
  q            ออก"""

FLYWHEEL_HELP = """  f            หมุนล้อค้างไว้ที่ความเร็วยิง (เช็คทิศทาง/เสียง โดยไม่ต้องใส่ลูก)
  g            หยุดล้อ
  ⚠ 't' จะเร่งล้อแล้วค้างไว้ให้ป้อนลูกเองประมาณ {window:.1f} วิ แล้วหยุด
"""

CROSSBOW_HELP = """  x            อ่านสถานะ cam_switch ตอนนี้ (True=ไม่สัมผัส, False=สัมผัส/พร้อมยิง)
"""


def build_help() -> str:
    tail = (FLYWHEEL_HELP.format(window=config.FLYWHEEL_FEED_WINDOW_S)
            if config.LAUNCHER == "flywheel" else CROSSBOW_HELP)
    return f"{COMMON_HELP}\n{tail}"


HELP = build_help()

def main():
    print(f"กลไกยิง = {config.LAUNCHER} (เปลี่ยนได้ที่ config.LAUNCHER)")
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
                if config.LAUNCHER == "flywheel":
                    print(f"\nเร่งล้อ {config.FLYWHEEL_SPINUP_S:.1f} วิ แล้วค้างไว้ "
                          f"{config.FLYWHEEL_FEED_WINDOW_S:.1f} วิ — หย่อนลูกตอนล้อนิ่งแล้ว "
                          f"(มุมเงย {turret.tilt_angle:.0f}°) ...")
                else:
                    print(f"\nยิง 1 นัด (มุมเงย {turret.tilt_angle:.0f}°) ...")
                turret.fire()
            elif cmd == "f" and config.LAUNCHER == "flywheel":
                print(f"\nหมุนล้อค้างที่ duty {config.FLYWHEEL_DUTY:.2f} — กด 'g' เพื่อหยุด")
                turret.spin_up()
            elif cmd == "g" and config.LAUNCHER == "flywheel":
                turret.spin_down()
                print("\nหยุดล้อแล้ว")
            elif cmd == "x" and config.LAUNCHER == "crossbow":
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
