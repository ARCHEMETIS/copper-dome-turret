# =============================================================
# ranging.py — วัดระยะจากขนาดวัตถุในภาพ + แปลงระยะเป็นความแรงล้อ (duty)
# =============================================================
import numpy as np

import config


def distance_mm(detection) -> float:
    """ระยะ = focal_px * ขนาดจริง / ขนาดในภาพ
    ขนาดในภาพใช้ √(กว้าง·สูง) ของกรอบ ไม่ใช่ความกว้างเดี่ยวๆ — วันจริง
    ตุ๊กตาถูกวางท่าไหนก็ได้ (หันเฉียง/นอน/หงายท้อง) ซึ่งทำให้ w หรือ h
    เดี่ยวๆ แกว่งแรง แต่พื้นที่เงาของตุ๊กตาทรงอ้วนกลมเปลี่ยนน้อยกว่ามาก
    (หมุน 90° = w↔h สลับกัน √(w·h) เท่าเดิม)
    ต้อง calibrate FOCAL_PX + real_size_mm ก่อน (tools/fit_focal.py)"""
    if config.FOCAL_PX is None:
        raise RuntimeError("ยังไม่ได้ calibrate FOCAL_PX — รัน tools/fit_focal.py ก่อน")
    real = config.TARGETS[detection.label]["real_size_mm"]
    size_px = (detection.w_px * detection.h_px) ** 0.5
    return config.FOCAL_PX * real / size_px


def duty_for_distance(dist_mm: float) -> float:
    """interpolate จากตาราง PWM_DISTANCE_TABLE (ยิงจริงวัดจริงเท่านั้นถึงจะแม่น)"""
    table = sorted(config.PWM_DISTANCE_TABLE)
    dists = [d for d, _ in table]
    duties = [p for _, p in table]
    duty = float(np.interp(dist_mm, dists, duties))
    return max(config.FLYWHEEL_MIN_DUTY, min(config.FLYWHEEL_MAX_DUTY, duty))
