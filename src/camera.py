# =============================================================
# camera.py — เปิดกล้อง (มือถือผ่าน Camo/DroidCam จะโผล่เป็น webcam ปกติ)
#
# ทำไมต้องลองหลาย backend: บนเครื่องนี้ interface DirectShow ของกล้องเสมือน
# Camo เสื่อมเรื้อรัง (เปิดได้ อ่านเฟรมได้ แต่ได้ "จอดำล้วน" — ใช้ได้แป๊บเดียว
# หลังรีสตาร์ท Camo Studio แล้วก็ดำอีก) ขณะที่ Media Foundation (MSMF)
# ให้ภาพจริงนิ่งตลอด — พิสูจน์ด้วยการ probe ทั้งคู่พร้อมกัน ณ เวลาเดียวกัน:
# DSHOW=0.0 (ดำ) / MSMF=168.3 (ภาพจริง)
# ดังนั้นการ "เปิดได้+อ่านได้" ไม่พอ ต้องเช็คด้วยว่าเฟรม "ไม่ใช่สีดำล้วน"
# ก่อนยอมรับ แล้วไล่ fallback ข้าม backend ให้เอง
# =============================================================
import time

import cv2

import config

# MSMF ก่อน (เสถียรกับกล้องเสมือนบนเครื่องนี้) แล้วค่อย DSHOW (เปิดเร็วกว่า
# กับกล้องฮาร์ดแวร์จริงบางตัว)
_BACKENDS = [(cv2.CAP_MSMF, "MSMF"), (cv2.CAP_DSHOW, "DSHOW")]

_WARMUP_FRAMES = 25          # อ่านสูงสุดกี่เฟรมระหว่างรอสตรีมตื่น (~2 วิ)
_MIN_BRIGHTNESS = 1.0        # ต่ำกว่านี้ถือว่า "ดำล้วน" (ห้องมืดจริงยังสว่างกว่านี้)
_POST_MODE_BRIGHT_FRAMES = 3  # ต้องเห็นเฟรมสว่างติดกันหลัง cap.set ไม่ใช่แค่เฟรมก่อนเปลี่ยนโหมด


def _record_size_mismatch(size_errors, index: int, name: str, frame):
    if size_errors is None or frame is None or len(frame.shape) < 2:
        return
    fh, fw = frame.shape[:2]
    message = f"{name} index {index}: {fw}x{fh}"
    if message not in size_errors:
        size_errors.append(message)


def _try_open(index: int, backend: int, name: str, size_errors=None) -> cv2.VideoCapture | None:
    """เปิดกล้อง 1 ตัวด้วย backend ที่ระบุ + ตรวจว่าได้ภาพจริงไม่ใช่จอดำ"""
    cap = cv2.VideoCapture(index, backend)
    if not cap.isOpened():
        return None

    for _ in range(_WARMUP_FRAMES):
        ok, frame = cap.read()
        if ok and frame is not None and frame.mean() > _MIN_BRIGHTNESS:
            # ได้ภาพจริงแล้ว — ตั้ง resolution เฉพาะตอนที่ไม่ตรงเท่านั้น
            # (สั่ง set ใส่กล้องเสมือนทั้งที่ค่าตรงอยู่แล้ว จะทำ stream
            # พังค้างเป็นจอดำจนต้องรีสตาร์ทแอปกล้อง — เจอจริงกับ Camo)
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            if (w, h) != (config.FRAME_WIDTH, config.FRAME_HEIGHT):
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.FRAME_WIDTH)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_HEIGHT)
                # Camo เคยเปิดได้และให้เฟรมสว่างก่อน set แต่เปลี่ยนโหมดแล้วกลายเป็นจอดำ
                # เฟรมเก่าที่ค้างอยู่จึงห้ามนับ — ต้องได้เฟรมสว่างติดกันหลังเปลี่ยนโหมดจริงๆ
                bright_after_mode = 0
                for _ in range(_WARMUP_FRAMES):
                    ok, f2 = cap.read()
                    if ok and f2 is not None:
                        fh2, fw2 = f2.shape[:2]
                        if (fw2, fh2) == (config.FRAME_WIDTH, config.FRAME_HEIGHT) \
                                and f2.mean() > _MIN_BRIGHTNESS:
                            frame = f2
                            bright_after_mode += 1
                            if bright_after_mode >= _POST_MODE_BRIGHT_FRAMES:
                                break
                        else:
                            if (fw2, fh2) != (config.FRAME_WIDTH, config.FRAME_HEIGHT):
                                _record_size_mismatch(size_errors, index, name, f2)
                            bright_after_mode = 0
                    else:
                        bright_after_mode = 0
                    time.sleep(0.08)
                else:
                    cap.release()
                    return None

            # เช็คทั้งกว้างและสูงจาก "เฟรมจริง" ไม่ใช่ค่า property (กล้องเสมือนบางตัว
            # ตอบรับคำสั่ง set แต่ส่งภาพเดิมมาเฉยๆ) — 1280x960 ห้ามผ่านเมื่อระบบใช้ 1280x720:
            # FOCAL_PX คาลิเบรตไว้ที่ FRAME_WIDTH ระยะทุกค่าจะเพี้ยนตามสัดส่วน
            # และ scope zero/พื้นที่กรอบจะเพี้ยนแบบเงียบๆ (ยิงตกทุกนัด)
            fh, fw = frame.shape[:2]
            if (fw, fh) != (config.FRAME_WIDTH, config.FRAME_HEIGHT):
                _record_size_mismatch(size_errors, index, name, frame)
                cap.release()
                return None
            print(f"[camera] เปิดกล้อง index {index} สำเร็จ ({name}, {fw}x{fh})")
            return cap
        time.sleep(0.08)

    cap.release()
    return None


def open_camera() -> cv2.VideoCapture:
    """เปิดกล้องตาม config ถ้าไม่ระบุ index จะไล่หา 0-5 ให้เอง
    ไล่ลองทุก backend และรับเฉพาะกล้องที่ให้ภาพจริง (ไม่ใช่จอดำ)"""
    indexes = [config.CAMERA_INDEX] if config.CAMERA_INDEX is not None else range(6)
    saw_black_only = False
    size_errors = []

    for i in indexes:
        for backend, name in _BACKENDS:
            cap = _try_open(i, backend, name, size_errors)
            if cap is not None:
                return cap
        # แยกเคส "ไม่มีกล้อง" กับ "มีแต่จอดำ" เพื่อ error message ที่ตรงจุด
        probe = cv2.VideoCapture(i, cv2.CAP_MSMF)
        if probe.isOpened():
            ok, f = probe.read()
            if ok and f is not None and f.mean() <= _MIN_BRIGHTNESS:
                saw_black_only = True
        probe.release()

    if saw_black_only:
        if size_errors:
            raise RuntimeError(
                "กล้องบาง backend ส่งภาพดำล้วน และ backend อื่นส่งขนาดไม่ตรง — "
                f"ขนาดที่พบ: {', '.join(size_errors)}; "
                "เช็ค Camo Studio และตั้ง resolution ให้ตรงกับ config.py"
            )
        raise RuntimeError(
            "กล้องเปิดได้แต่ส่งภาพดำล้วนมาตลอด — เช็คตามลำดับ: "
            "1) จอมือถือติดอยู่และแอป Camo อยู่หน้าสุด "
            "2) Camo Studio บนคอมเห็นภาพสด "
            "3) ปิด-เปิด Camo Studio ใหม่"
        )
    if size_errors:
        raise RuntimeError(
            f"กล้องทุก backend ส่งขนาดภาพไม่ตรง — ระบบต้องการ "
            f"{config.FRAME_WIDTH}x{config.FRAME_HEIGHT}, แต่พบ {', '.join(size_errors)}; "
            "ตั้ง resolution ใน Camo Studio ให้ตรง หรือแก้ config พร้อมคาลิเบรตใหม่"
        )
    raise RuntimeError(
        "หากล้องไม่เจอ — เช็คว่า Camo/DroidCam ต่ออยู่ แล้วลองตั้ง CAMERA_INDEX ใน config.py"
    )
