# =============================================================
# test_catapult.py — ทดสอบ XRP catapult launcher (slip-gear, DC gearmotor เดียว)
# ต่างจาก flywheel: มอเตอร์ตัวเดียว หมุนทิศเดียวต่อเนื่อง ไม่ต้องมี servo แยกยิง
# กลไก slip-gear ดึงยางยืด -> หลุดเอง -> ดีด -> หมุนต่อกลับที่พร้อมยิงใหม่
# รัน: python tools/test_catapult.py
# แก้ pin ด้านล่างให้ตรงกับที่ต่อสายจริงก่อนรัน (ยังไม่ผูกกับ config.py
# เพราะยังไม่ตัดสินใจว่าจะใช้ catapult หรือ flywheel เป็นกลไกจริง)
# =============================================================
import msvcrt
import sys
import time
from pathlib import Path

from pyfirmata2 import Arduino

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import config

PIN_MOTOR_PWM = 5    # PWM -> ENA ของ L298N (หรือ driver มอเตอร์ตัวเดียวที่ใช้)
PIN_MOTOR_IN1 = 2    # ทิศทาง — slip-gear หมุนทิศเดียว ไม่ต้องสลับ
PIN_MOTOR_IN2 = 4

HELP = """
กดปุ่มเดียวสั่งได้เลย ไม่ต้อง Enter:
  0-9   ตั้งความเร็วมอเตอร์ (0=หยุด, 9=90%) แล้วปล่อยหมุนต่อเนื่อง
        ดูจังหวะ: ดึงยาง -> หลุด -> ดีด -> หมุนกลับที่พร้อมยิง (วนเอง)
  s     หยุดมอเตอร์ทันที
  q     ออก
"""


def set_speed(pwm, current: float, target: float) -> float:
    """ขาขึ้น soft-start ไต่ทีละขั้นเหมือน flywheel (แบตวูบจน L298N ดับ 15 ก.ค.)
    catapult หนักกว่าตอนดึงยาง ยิ่งต้อง ramp. ขาลง/หยุด สั่งทันที"""
    while current + config.DRAW_RAMP_STEP < target:
        current += config.DRAW_RAMP_STEP
        pwm.write(current)
        time.sleep(config.DRAW_RAMP_STEP_S)
    pwm.write(target)
    return target


def main():
    port = config.SERIAL_PORT or Arduino.AUTODETECT
    print("กำลังต่อ Arduino ...")
    board = Arduino(port)
    time.sleep(2)  # Uno รีเซ็ตตัวเองตอนเปิด serial

    pwm = board.get_pin(f"d:{PIN_MOTOR_PWM}:p")
    in1 = board.get_pin(f"d:{PIN_MOTOR_IN1}:o")
    in2 = board.get_pin(f"d:{PIN_MOTOR_IN2}:o")
    in1.write(1)
    in2.write(0)
    pwm.write(0.0)

    print("ต่อสำเร็จ!", HELP)
    duty = 0.0
    try:
        while True:
            print(f"\r[duty={duty:.1f}] > ", end="", flush=True)
            cmd = msvcrt.getwch()  # อ่านทีละปุ่ม ไม่ต้องรอ Enter
            if cmd.lower() == "q":
                print()
                break
            elif cmd.lower() == "s":
                duty = 0.0
                pwm.write(duty)
                print("\nหยุดมอเตอร์")
            elif cmd.isdigit():
                duty = set_speed(pwm, duty, int(cmd) / 10)
                print(f"\nมอเตอร์หมุนที่ {duty * 100:.0f}%")
            elif cmd in ("\r", "\n"):
                pass  # เผลอกด Enter = เฉยๆ ไม่ต้องโชว์ help
            else:
                print(HELP)
    finally:
        pwm.write(0.0)
        board.exit()
        print("ปิดบอร์ดเรียบร้อย")


if __name__ == "__main__":
    main()
