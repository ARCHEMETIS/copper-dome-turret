# =============================================================
# ranging.py — วัดระยะจากขนาดวัตถุในภาพ + แปลงระยะเป็นความแรงล้อ (duty)
# =============================================================
import numpy as np

import config


def distance_mm(detection) -> float:
    """ระยะ = focal_px * ขนาดจริง / ขนาดในภาพ
    ต้อง calibrate FOCAL_PX ก่อน (tools/calibrate_focal.py) และล็อก focus มือถือ"""
    if config.FOCAL_PX is None:
        raise RuntimeError("ยังไม่ได้ calibrate FOCAL_PX — รัน tools/calibrate_focal.py ก่อน")
    real_w = config.TARGETS[detection.label]["real_width_mm"]
    return config.FOCAL_PX * real_w / detection.w_px


def duty_for_distance(dist_mm: float) -> float:
    """interpolate จากตาราง PWM_DISTANCE_TABLE (ยิงจริงวัดจริงเท่านั้นถึงจะแม่น)"""
    table = sorted(config.PWM_DISTANCE_TABLE)
    dists = [d for d, _ in table]
    duties = [p for _, p in table]
    duty = float(np.interp(dist_mm, dists, duties))
    return max(config.FLYWHEEL_MIN_DUTY, min(config.FLYWHEEL_MAX_DUTY, duty))
