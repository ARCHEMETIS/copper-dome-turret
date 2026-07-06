# =============================================================
# hardware.py — ชั้นเดียวที่คุยกับ Arduino (ผ่าน pyfirmata2)
# ไฟล์อื่นห้ามแตะ pyfirmata2 ตรงๆ ให้เรียกผ่านคลาส Turret เท่านั้น
#
# ก่อนใช้: อัปโหลด StandardFirmata ลง Uno ครั้งเดียวผ่าน Arduino IDE
#   File > Examples > Firmata > StandardFirmata > Upload
# หลังจากนั้นไม่ต้องเขียน/แตะโค้ด Arduino อีกเลย
# =============================================================
import time

from pyfirmata2 import Arduino

import config


class Turret:
    def __init__(self, port: str | None = None):
        port = port or config.SERIAL_PORT or Arduino.AUTODETECT
        self.board = Arduino(port)
        time.sleep(2)  # Uno รีเซ็ตตัวเองตอนเปิด serial — ต้องรอ

        self.pan = self.board.get_pin(f"d:{config.PIN_PAN_SERVO}:s")
        self.feeder = self.board.get_pin(f"d:{config.PIN_FEEDER_SERVO}:s")
        self.ena = self.board.get_pin(f"d:{config.PIN_FLYWHEEL_ENA}:p")
        self.enb = self.board.get_pin(f"d:{config.PIN_FLYWHEEL_ENB}:p")
        in1 = self.board.get_pin(f"d:{config.PIN_IN1}:o")
        in2 = self.board.get_pin(f"d:{config.PIN_IN2}:o")
        in3 = self.board.get_pin(f"d:{config.PIN_IN3}:o")
        in4 = self.board.get_pin(f"d:{config.PIN_IN4}:o")

        # ตั้งทิศทางมอเตอร์ครั้งเดียว: สองล้อหมุนสวนกันเพื่อหนีบลูกออกไปข้างหน้า
        # ถ้าลูก "ถูกดูดเข้า" แทนที่จะพุ่งออก ให้สลับ 1/0 ของคู่ใดคู่หนึ่ง
        in1.write(1)
        in2.write(0)
        in3.write(0)
        in4.write(1)

        self._pan_angle = float(config.PAN_CENTER)
        self.pan.write(self._pan_angle)
        self.feeder.write(config.FEEDER_REST)
        self.set_flywheel(0.0)
        time.sleep(0.5)

    # ---------- Pan ----------
    @property
    def pan_angle(self) -> float:
        return self._pan_angle

    def pan_to(self, angle: float):
        angle = max(config.PAN_MIN, min(config.PAN_MAX, angle))
        self._pan_angle = angle
        self.pan.write(angle)

    def pan_by(self, delta_deg: float):
        self.pan_to(self._pan_angle + delta_deg)

    # ---------- Flywheel ----------
    def set_flywheel(self, duty: float):
        """duty 0..1 (0 = หยุด). ค่าต่ำกว่า FLYWHEEL_MIN_DUTY ล้ออาจไม่หมุน"""
        duty = max(0.0, min(config.FLYWHEEL_MAX_DUTY, duty))
        self.ena.write(duty)
        self.enb.write(duty)

    # ---------- Feeder ----------
    def feed_one(self):
        """ดันลูก 1 ลูกเข้าล้อ แล้วถอยกลับที่พัก"""
        self.feeder.write(config.FEEDER_PUSH)
        time.sleep(config.FEEDER_PUSH_TIME_S)
        self.feeder.write(config.FEEDER_REST)
        time.sleep(config.FEEDER_RETURN_TIME_S)

    # ---------- ยิง 1 นัด (รวมจังหวะทั้งหมด) ----------
    def fire(self, duty: float):
        self.set_flywheel(duty)
        time.sleep(config.FLYWHEEL_SPINUP_S)
        self.feed_one()
        time.sleep(0.3)  # ให้ลูกพ้นล้อก่อนค่อยหยุด
        self.set_flywheel(0.0)

    def close(self):
        try:
            self.set_flywheel(0.0)
            self.feeder.write(config.FEEDER_REST)
        finally:
            self.board.exit()
