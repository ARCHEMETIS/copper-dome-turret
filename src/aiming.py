# =============================================================
# aiming.py — visual servoing: หมุนป้อมทีละนิดจนเป้าอยู่ที่ "จุด zero" ของสโคป
# หลักการ: ไม่ต้องรู้ตำแหน่งเป้าเป๊ะๆ แค่ดู error ในภาพแล้วหมุนลด error
# (move → stop → check ซ้ำๆ) เลยรองรับ "เป้าวางตรงไหนก็ได้" ตามโจทย์
#
# โหมดสโคป (18 ก.ค.): กล้องติดไปกับลำกล้อง (pan+tilt ตาม) จุด zero คือพิกเซลที่
# คาลิเบรตจากการยิงจริงว่า "เป้าอยู่ตรงนี้ = โดน" — เล็งจึงเป็น 2 แกน:
# pan ลด error แนวนอน, tilt ลด error แนวตั้ง ไม่มีการวัดระยะ/ตั้งมุมตามระยะ
# =============================================================
import time

import config


def _step(error_px: float) -> float:
    step = config.AIM_KP * error_px
    return max(-config.AIM_MAX_STEP_DEG, min(config.AIM_MAX_STEP_DEG, step))


def _read_fresh(cap):
    """อ่านเฟรม "ล่าสุด" — ทิ้งเฟรมค้างใน buffer ก่อน กัน servo เล็งจากภาพ "ก่อนหมุน"
    (loop สั่งหมุน→รอ→อ่าน; ถ้า cap.read() คืนเฟรมเก่าสุดใน buffer = แก้ error จากภาพ
    ก่อนป้อมขยับ → อาการส่าย/ลู่เข้าช้า) ใช้ grab() ที่ไม่ decode (เร็ว) ถ้ามี —
    SimCamera ไม่มี grab ก็อ่านปกติ. ไม่แตะ property กล้องเลย (กัน Camo จอดำจาก
    cap.set — ดูเหตุผลใน camera.py)"""
    grab = getattr(cap, "grab", None)
    if grab is not None:
        for _ in range(config.AIM_FLUSH_FRAMES):
            grab()
    return cap.read()


def aim_at(turret, cap, detector, target: str, on_frame=None, should_abort=None):
    """เล็งเป้าจนอยู่ที่จุด zero ของสโคป (ทั้งสองแกน)

    on_frame: callback(frame, detection|None) เอาไว้ให้ UI วาดภาพระหว่างเล็ง (ใส่หรือไม่ก็ได้)
    should_abort: callable() -> bool เช็คทุกรอบลูป ถ้าคืน True เลิกเล็งทันที
                  (เช่น ตอนปิดโปรแกรมกลางคัน — จะได้ไม่ต้องรอจนหมด AIM_TIMEOUT_S)
    คืนค่า Detection ล่าสุด (เล็งสำเร็จ) หรือ None (หาไม่เจอ/หมดเวลา/ถูกยกเลิก)
    """
    deadline = time.time() + config.AIM_TIMEOUT_S
    confirmed = 0

    while time.time() < deadline:
        if should_abort is not None and should_abort():
            return None
        ok, frame = _read_fresh(cap)
        if not ok:
            continue
        det = detector.detect(frame, target)
        if on_frame:
            on_frame(frame, det)

        if det is None:
            # ยังไม่เห็นเป้า — กวาดหาช้าๆ ไปทางขวาจนสุด แล้วเด้งกลับซ้าย (pan อย่างเดียว
            # tilt ปล่อยไว้ที่เดิม — เป้าอยู่ระดับโต๊ะเดียวกันหมด แนวตั้งไม่ต้องกวาด)
            confirmed = 0
            if turret.pan_angle >= config.PAN_MAX:
                turret.pan_to(config.PAN_MIN)
            else:
                turret.pan_by(4)
            time.sleep(config.AIM_SETTLE_S)
            continue

        zero_x = frame.shape[1] / 2 + config.SCOPE_ZERO_OFFSET_PX[0]
        zero_y = frame.shape[0] / 2 + config.SCOPE_ZERO_OFFSET_PX[1]
        err_x = det.cx - zero_x   # +ค่า = เป้าอยู่ขวาของจุด zero
        err_y = det.cy - zero_y   # +ค่า = เป้าอยู่ใต้จุด zero → ต้องก้มลง

        if abs(err_x) <= config.AIM_DEADBAND_PX and abs(err_y) <= config.AIM_DEADBAND_PX:
            confirmed += 1
            if confirmed >= config.AIM_CONFIRM_FRAMES:
                return det  # นิ่งที่จุด zero ติดกันพอแล้ว → พร้อมยิง
            time.sleep(config.AIM_CONFIRM_POLL_S)
            continue

        confirmed = 0
        if abs(err_x) > config.AIM_DEADBAND_PX:
            turret.pan_by(config.AIM_SIGN * _step(err_x))    # หมุนหนีเป้า → แก้ AIM_SIGN
        if abs(err_y) > config.AIM_DEADBAND_PX:
            turret.tilt_by(-config.AIM_TILT_SIGN * _step(err_y))  # เงยหนีเป้า → แก้ AIM_TILT_SIGN
        time.sleep(config.AIM_SETTLE_S)

    return None  # หมดเวลา — ถ้าเล็งสำเร็จจะ return ในลูปไปแล้ว (ตรง confirmed ครบ)
