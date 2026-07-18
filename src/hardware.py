# =============================================================
# hardware.py — ชั้นเดียวที่คุยกับ Arduino (ผ่าน pyfirmata2)
# ไฟล์อื่นห้ามแตะ pyfirmata2 ตรงๆ ให้เรียกผ่านคลาส Turret เท่านั้น
#
# กลไกยิง = หน้าไม้ (crossbow): pan+tilt servo เล็ง → มอเตอร์ดึงสาย 2 ตัวหมุน
# เฟืองครึ่งวง (half-gear) จนฟันหมด → ยางดีดเอง → เฟืองหมุนต่อกลับที่ตำแหน่ง
# "พร้อมยิง" อัตโนมัติ (self-cycling) แมกกาซีน gravity-feed ป้อนลูกใหม่เอง
# ไม่ต้องมี feeder servo แยก (ดู docs/แผนโปรเจค-CopperDome.md §2.5)
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
        self.tilt = self.board.get_pin(f"d:{config.PIN_TILT_SERVO}:s")
        self.ena = self.board.get_pin(f"d:{config.PIN_DRAW_ENA}:p")
        self.enb = self.board.get_pin(f"d:{config.PIN_DRAW_ENB}:p")
        in1 = self.board.get_pin(f"d:{config.PIN_IN1}:o")
        in2 = self.board.get_pin(f"d:{config.PIN_IN2}:o")
        in3 = self.board.get_pin(f"d:{config.PIN_IN3}:o")
        in4 = self.board.get_pin(f"d:{config.PIN_IN4}:o")
        self.cam_switch = self.board.get_pin(f"d:{config.PIN_CAM_SWITCH}:u")  # 'u' = INPUT_PULLUP

        # ตั้งทิศทางมอเตอร์ครั้งเดียว: มอเตอร์ดึงสาย 2 ตัวหมุน "ทิศเดียวกัน" (ดึงเข้าหาตัว)
        # ถ้าตัวไหนดึงกลับทาง (ผ่อนสายแทนดึง) ให้สลับ 1/0 ของคู่ IN ตัวนั้น
        in1.write(1)
        in2.write(0)
        in3.write(1)
        in4.write(0)

        self.board.samplingOn()  # เปิด background thread อ่านค่า digital input (cam_switch)

        self._pan_angle = float(config.PAN_CENTER)
        self._tilt_angle = float(config.TILT_CENTER)
        self._duty = 0.0
        self.pan.write(self._pan_angle)
        self.tilt.write(self._tilt_angle)
        self.set_draw(0.0)
        time.sleep(0.5)

    # ---------- Pan / Tilt (servo ทั้งคู่ใช้จุดหมุนร่วมกัน) ----------
    def _move_servo(self, pin, current: float, angle: float, lo: float, hi: float) -> float:
        angle = max(lo, min(hi, angle))
        pin.write(angle)
        return angle

    @property
    def pan_angle(self) -> float:
        return self._pan_angle

    def pan_to(self, angle: float):
        self._pan_angle = self._move_servo(self.pan, self._pan_angle, angle,
                                           config.PAN_MIN, config.PAN_MAX)

    def pan_by(self, delta_deg: float):
        self.pan_to(self._pan_angle + delta_deg)

    # ---------- Tilt (มุมเงย — คุมระยะยิง) ----------
    @property
    def tilt_angle(self) -> float:
        return self._tilt_angle

    def tilt_to(self, angle: float):
        self._tilt_angle = self._move_servo(self.tilt, self._tilt_angle, angle,
                                            config.TILT_MIN, config.TILT_MAX)
        time.sleep(config.TILT_SETTLE_S)

    def tilt_by(self, delta_deg: float):
        self.tilt_to(self._tilt_angle + delta_deg)

    # ---------- มอเตอร์ดึงสาย ----------
    def set_draw(self, duty: float):
        """duty 0..1 (0 = หยุด). ค่าคงที่เดียว (config.DRAW_DUTY) ใช้ทุกนัด — ไม่ผันตามระยะ
        เหมือน flywheel เดิม (ระยะคุมด้วยมุมเงยแทน) ขาขึ้น soft-start ไต่ทีละขั้น (ดูเหตุผลใน
        config) ขาลง/หยุด สั่งทันที"""
        duty = max(0.0, min(config.DRAW_MAX_DUTY, duty))
        while self._duty + config.DRAW_RAMP_STEP < duty:
            self._duty += config.DRAW_RAMP_STEP
            self.ena.write(self._duty)
            self.enb.write(self._duty)
            time.sleep(config.DRAW_RAMP_STEP_S)
        self._duty = duty
        self.ena.write(duty)
        self.enb.write(duty)

    def _wait_for_switch(self, want_value: bool, deadline: float):
        """รอจน cam_switch.value == want_value เป๊ะๆ (True=ไม่สัมผัส, False=สัมผัส GND)
        เทียบด้วย `is not want_value` ไม่ใช่ `is (not want_value)` — เพราะ pyfirmata2 ปล่อยให้
        .value เป็น None อยู่ช่วงสั้นๆ หลัง samplingOn() ก่อนรายงานรอบแรกเข้ามา ถ้าเทียบแบบ
        `is False`/`is True` ตรงๆ ค่า None จะไม่ตรงเงื่อนไขไหนเลยแล้วข้ามรอทั้งเฟสไปเงียบๆ"""
        while self.cam_switch.value is not want_value:
            if time.time() > deadline:
                self.set_draw(0.0)
                raise TimeoutError(
                    "เฟืองดึงหมุนไม่ครบรอบภายใน timeout — เช็คสายสวิตช์ (cam_switch) "
                    "หรือมอเตอร์ติดขัด")
            time.sleep(0.01)

    def draw_and_release(self):
        """ดึงสายจนเฟืองครึ่งวงหลุด (ยางดีดลูกออกเอง) แล้วหมุนต่อกลับตำแหน่งพร้อมยิง
        ใหม่ (self-cycling) จับจังหวะด้วย cam_switch (สัมผัส GND แค่ตอนอยู่ตำแหน่ง
        พร้อมยิง 1 จุดต่อรอบ) ไม่ใช้เวลานับเพราะความเร็วมอเตอร์ไม่คงที่จริง"""
        self.set_draw(config.DRAW_DUTY)
        deadline = time.time() + config.DRAW_TIMEOUT_S
        # เฟส 1: รอให้ "หลุด" จากจุดสัมผัสก่อน (เผื่อเริ่มต้นเฟืองค้างอยู่ที่จุดพร้อมยิงพอดี)
        self._wait_for_switch(want_value=True, deadline=deadline)
        # เฟส 2: รอให้ "สัมผัสอีกครั้ง" = ครบ 1 รอบเต็ม = ดีดออกแล้ว กลับมาพร้อมยิงนัดต่อไป
        self._wait_for_switch(want_value=False, deadline=deadline)
        self.set_draw(0.0)

    # ---------- ยิง 1 นัด (รวมจังหวะทั้งหมด) ----------
    def fire(self, tilt_angle: float):
        """ตั้งมุมเงยตามระยะ (จาก ranging.angle_for_distance) แล้วดึง+ปล่อย 1 นัด
        แมกกาซีน gravity-feed ป้อนลูกใหม่เข้ารางเองหลังนัดก่อนหน้า ไม่ต้อง feed แยก"""
        self.tilt_to(tilt_angle)
        self.draw_and_release()

    def close(self):
        try:
            self.set_draw(0.0)
        finally:
            self.board.exit()
