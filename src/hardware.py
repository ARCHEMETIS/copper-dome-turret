# =============================================================
# hardware.py — ชั้นเดียวที่คุยกับ Arduino (ผ่าน pyfirmata2)
# ไฟล์อื่นห้ามแตะ pyfirmata2 ตรงๆ ให้เรียกผ่านคลาส Turret เท่านั้น
#
# รองรับกลไกยิง 2 แบบ สลับด้วย config.LAUNCHER บรรทัดเดียว (กลไกเปลี่ยนมา 2 รอบแล้ว):
#
#   "flywheel" (ค่าเริ่มต้น 20 ก.ค. 2026) — ล้อ 2 ตัวหมุนสวนกันหนีบลูกออกไป
#       ยิงแรงคงที่ วิถีแบน (เพื่อนทดสอบแล้ว) ป้อนลูกด้วยมือ/แรงโน้มถ่วงในหน้าต่างเวลาที่
#       ล้อค้างความเร็วเต็มไว้ — ไม่มี feeder servo เพราะ servo ตัวที่ 2 ไปเป็น tilt
#
#   "crossbow" (18 ก.ค. — เก็บไว้เผื่อสลับกลับ) — มอเตอร์ดึงสายผ่านเฟืองครึ่งวงจนฟันหมด
#       ยางดีดเอง แล้วหมุนต่อกลับตำแหน่งพร้อมยิงเอง (self-cycling) จับจังหวะด้วย cam_switch
#
# ทั้งสองแบบใช้สายชุดเดียวกัน (L298N + มอเตอร์ DC 2 ตัว + servo 2 ตัว) ต่างกันแค่
# ทิศทางมอเตอร์กับการมี cam_switch — ส่วนการเล็ง (pan/tilt โหมดสโคป) เหมือนกันทั้งคู่
#
# ก่อนใช้: อัปโหลด StandardFirmata ลง Uno ครั้งเดียวผ่าน Arduino IDE
#   File > Examples > Firmata > StandardFirmata > Upload
# หลังจากนั้นไม่ต้องเขียน/แตะโค้ด Arduino อีกเลย
# =============================================================
import time

from pyfirmata2 import Arduino

import config

VALID_LAUNCHERS = ("flywheel", "crossbow")


class Turret:
    def __init__(self, port: str | None = None):
        if config.LAUNCHER not in VALID_LAUNCHERS:
            raise ValueError(
                f"config.LAUNCHER = {config.LAUNCHER!r} ไม่ถูกต้อง "
                f"— ต้องเป็นหนึ่งใน {VALID_LAUNCHERS}")
        self.launcher = config.LAUNCHER
        self._is_crossbow = self.launcher == "crossbow"

        # ค่า ramp/เพดาน duty คนละชุดตามกลไก (อ่านครั้งเดียวตอนเปิด ไม่ต้องแตะ config ทุกนัด)
        if self._is_crossbow:
            self._ramp_step = config.DRAW_RAMP_STEP
            self._ramp_step_s = config.DRAW_RAMP_STEP_S
            self._max_duty = config.DRAW_MAX_DUTY
        else:
            self._ramp_step = config.FLYWHEEL_RAMP_STEP
            self._ramp_step_s = config.FLYWHEEL_RAMP_STEP_S
            self._max_duty = config.FLYWHEEL_MAX_DUTY

        port = port or config.SERIAL_PORT or Arduino.AUTODETECT
        self.board = Arduino(port)
        time.sleep(2)  # Uno รีเซ็ตตัวเองตอนเปิด serial — ต้องรอ

        self.pan = self.board.get_pin(f"d:{config.PIN_PAN_SERVO}:s")
        self.tilt = self.board.get_pin(f"d:{config.PIN_TILT_SERVO}:s")
        self.ena = self.board.get_pin(f"d:{config.PIN_MOTOR_ENA}:p")
        self.enb = self.board.get_pin(f"d:{config.PIN_MOTOR_ENB}:p")
        in1 = self.board.get_pin(f"d:{config.PIN_IN1}:o")
        in2 = self.board.get_pin(f"d:{config.PIN_IN2}:o")
        in3 = self.board.get_pin(f"d:{config.PIN_IN3}:o")
        in4 = self.board.get_pin(f"d:{config.PIN_IN4}:o")

        # ตั้งทิศทางมอเตอร์ครั้งเดียว — ต่างกันตามกลไก
        # ถ้าหมุนผิดทาง (ลูกถูกดูดเข้าแทนพุ่งออก / ดึงสายไม่เข้า) สลับ 1/0 ของคู่ IN ตัวนั้น
        in1.write(1)
        in2.write(0)
        if self._is_crossbow:
            in3.write(1)   # ทิศเดียวกับตัวแรก = ดึงสายเข้าหาตัวพร้อมกัน
            in4.write(0)
        else:
            in3.write(0)   # สวนทางตัวแรก = สองล้อหนีบลูกออกไปข้างหน้า
            in4.write(1)

        # cam_switch มีเฉพาะหน้าไม้ — โหมด flywheel ไม่ต่อสายเส้นนี้ จึงไม่เปิด sampling
        # (ถ้าเปิดทิ้งไว้ทั้งที่ไม่มีสวิตช์ = เสีย thread เปล่าและอ่านได้ค่าลอยๆ)
        self.cam_switch = None
        if self._is_crossbow:
            self.cam_switch = self.board.get_pin(f"d:{config.PIN_CAM_SWITCH}:u")  # 'u' = INPUT_PULLUP
            self.board.samplingOn()  # background thread อ่านค่า digital input

        self._pan_angle = float(config.PAN_CENTER)
        self._tilt_angle = float(config.TILT_CENTER)
        self._duty = 0.0
        self.pan.write(self._pan_angle)
        self.tilt.write(self._tilt_angle)
        self.set_motor_duty(0.0)
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

    # ---------- Tilt (แกนเล็งแนวตั้ง — โหมดสโคป ไม่ใช่ตัวคุมระยะ) ----------
    @property
    def tilt_angle(self) -> float:
        return self._tilt_angle

    def tilt_to(self, angle: float):
        self._tilt_angle = self._move_servo(self.tilt, self._tilt_angle, angle,
                                            config.TILT_MIN, config.TILT_MAX)

    def tilt_by(self, delta_deg: float):
        self.tilt_to(self._tilt_angle + delta_deg)

    # ---------- มอเตอร์ (ล้อยิง หรือ มอเตอร์ดึงสาย — ใช้ ENA/ENB คู่เดียวกัน) ----------
    def set_motor_duty(self, duty: float):
        """duty 0..1 (0 = หยุด) ขาขึ้น soft-start ไต่ทีละขั้น ขาลง/หยุด สั่งทันที

        soft-start จำเป็นจริง: มอเตอร์ออกตัวกระชากกระแสหลายเท่าของตอนหมุนปกติ
        เคยทำแบตวูบจน L298N ดับทั้งบอร์ดมาแล้ว (15 ก.ค. กับ flywheel ชุดนี้เอง)"""
        duty = max(0.0, min(self._max_duty, duty))
        while self._duty + self._ramp_step < duty:
            self._duty += self._ramp_step
            self.ena.write(self._duty)
            self.enb.write(self._duty)
            time.sleep(self._ramp_step_s)
        self._duty = duty
        self.ena.write(duty)
        self.enb.write(duty)

    @property
    def motor_duty(self) -> float:
        return self._duty

    # ---------- ล้อยิง (flywheel) ----------
    def spin_up(self):
        """เร่งล้อขึ้นความเร็วยิงแล้วรอจนนิ่ง — แยกออกมาให้ UI สั่งค้างไว้เองได้
        ถ้าอยากยิงรัวโดยไม่ต้องเร่งใหม่ทุกนัด"""
        self.set_motor_duty(config.FLYWHEEL_DUTY)
        time.sleep(config.FLYWHEEL_SPINUP_S)

    def spin_down(self):
        self.set_motor_duty(0.0)

    def _fire_flywheel(self):
        """เร่งล้อจนนิ่ง → ค้างความเร็วไว้เป็นหน้าต่างให้คนหย่อนลูก → หยุดล้อ

        ไม่มี feeder servo (servo ตัวที่ 2 ไปเป็น tilt) — คนป้อนลูกเองในช่วงที่ล้อค้าง
        สำคัญ: ต้องรอ FLYWHEEL_SPINUP_S ให้ล้อนิ่งก่อนป้อน ไม่งั้นนัดนั้นเบากว่าเพื่อน
        แล้วจุดตกจะเพี้ยนจาก zero (โหมดสโคปตั้งอยู่บนสมมติฐานว่าทุกนัดแรงเท่ากัน)"""
        self.spin_up()
        time.sleep(config.FLYWHEEL_FEED_WINDOW_S)
        self.spin_down()

    # ---------- หน้าไม้ (crossbow) ----------
    def _wait_for_switch(self, want_value: bool, deadline: float):
        """รอจน cam_switch.value == want_value เป๊ะๆ (True=ไม่สัมผัส, False=สัมผัส GND)
        เทียบด้วย `is not want_value` ไม่ใช่ `is (not want_value)` — เพราะ pyfirmata2 ปล่อยให้
        .value เป็น None อยู่ช่วงสั้นๆ หลัง samplingOn() ก่อนรายงานรอบแรกเข้ามา ถ้าเทียบแบบ
        `is False`/`is True` ตรงๆ ค่า None จะไม่ตรงเงื่อนไขไหนเลยแล้วข้ามรอทั้งเฟสไปเงียบๆ"""
        while self.cam_switch.value is not want_value:
            if time.time() > deadline:
                self.set_motor_duty(0.0)
                raise TimeoutError(
                    "เฟืองดึงหมุนไม่ครบรอบภายใน timeout — เช็คสายสวิตช์ (cam_switch) "
                    "หรือมอเตอร์ติดขัด")
            time.sleep(0.01)

    def draw_and_release(self):
        """ดึงสายจนเฟืองครึ่งวงหลุด (ยางดีดลูกออกเอง) แล้วหมุนต่อกลับตำแหน่งพร้อมยิง
        ใหม่ (self-cycling) จับจังหวะด้วย cam_switch (สัมผัส GND แค่ตอนอยู่ตำแหน่ง
        พร้อมยิง 1 จุดต่อรอบ) ไม่ใช้เวลานับเพราะความเร็วมอเตอร์ไม่คงที่จริง"""
        self.set_motor_duty(config.DRAW_DUTY)
        deadline = time.time() + config.DRAW_TIMEOUT_S
        # เฟส 1: รอให้ "หลุด" จากจุดสัมผัสก่อน (เผื่อเริ่มต้นเฟืองค้างอยู่ที่จุดพร้อมยิงพอดี)
        self._wait_for_switch(want_value=True, deadline=deadline)
        # เฟส 2: รอให้ "สัมผัสอีกครั้ง" = ครบ 1 รอบเต็ม = ดีดออกแล้ว กลับมาพร้อมยิงนัดต่อไป
        self._wait_for_switch(want_value=False, deadline=deadline)
        self.set_motor_duty(0.0)

    # ---------- ยิง 1 นัด ----------
    def fire(self):
        """ยิง 1 นัดที่แรงเต็มคงที่ — โหมดสโคป: การเล็ง (pan+tilt เอาเป้าเข้าจุด zero)
        เสร็จก่อนเรียกยิงแล้ว ไม่มีการตั้งมุมตามระยะอีก"""
        if self._is_crossbow:
            self.draw_and_release()
        else:
            self._fire_flywheel()

    def close(self):
        try:
            self.set_motor_duty(0.0)
        finally:
            self.board.exit()
