# =============================================================
# aiming.py — visual servoing: หมุนป้อมทีละนิดจนเป้าอยู่กลางภาพ
# หลักการ: ไม่ต้องรู้ตำแหน่งเป้าเป๊ะๆ แค่ดู error ในภาพแล้วหมุนลด error
# (move → stop → check ซ้ำๆ) เลยรองรับ "เป้าวางตรงไหนก็ได้" ตามโจทย์
# =============================================================
import time

import config


def aim_at(turret, cap, detector, target: str, on_frame=None):
    """เล็งเป้าจนอยู่กลางภาพ

    on_frame: callback(frame, detection|None) เอาไว้ให้ UI วาดภาพระหว่างเล็ง (ใส่หรือไม่ก็ได้)
    คืนค่า Detection ล่าสุด (เล็งสำเร็จ) หรือ None (หาไม่เจอ/หมดเวลา)
    """
    deadline = time.time() + config.AIM_TIMEOUT_S
    confirmed = 0
    last_det = None

    while time.time() < deadline:
        ok, frame = cap.read()
        if not ok:
            continue
        det = detector.detect(frame, target)
        if on_frame:
            on_frame(frame, det)

        if det is None:
            # ยังไม่เห็นเป้า — กวาดหาช้าๆ ไปทางขวาจนสุด แล้วเด้งกลับซ้าย
            confirmed = 0
            if turret.pan_angle >= config.PAN_MAX:
                turret.pan_to(config.PAN_MIN)
            else:
                turret.pan_by(4)
            time.sleep(config.AIM_SETTLE_S)
            continue

        last_det = det
        error_px = det.cx - frame.shape[1] / 2  # +ค่า = เป้าอยู่ขวาของกลางภาพ

        if abs(error_px) <= config.AIM_DEADBAND_PX:
            confirmed += 1
            if confirmed >= config.AIM_CONFIRM_FRAMES:
                return det  # นิ่งกลางภาพติดกันพอแล้ว → พร้อมยิง
            time.sleep(0.05)
            continue

        confirmed = 0
        step = config.AIM_KP * error_px
        step = max(-config.AIM_MAX_STEP_DEG, min(config.AIM_MAX_STEP_DEG, step))
        turret.pan_by(config.AIM_SIGN * step)  # ถ้าหมุนหนีเป้า → แก้ AIM_SIGN ใน config
        time.sleep(config.AIM_SETTLE_S)

    return last_det if confirmed >= config.AIM_CONFIRM_FRAMES else None
