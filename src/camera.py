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


def _try_open(index: int, backend: int, name: str) -> cv2.VideoCapture | None:
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
            print(f"[camera] เปิดกล้อง index {index} สำเร็จ ({name}, {w}x{h})")
            return cap
        time.sleep(0.08)

    cap.release()
    return None


def open_camera() -> cv2.VideoCapture:
    """เปิดกล้องตาม config ถ้าไม่ระบุ index จะไล่หา 0-5 ให้เอง
    ไล่ลองทุก backend และรับเฉพาะกล้องที่ให้ภาพจริง (ไม่ใช่จอดำ)"""
    indexes = [config.CAMERA_INDEX] if config.CAMERA_INDEX is not None else range(6)
    saw_black_only = False

    for i in indexes:
        for backend, name in _BACKENDS:
            cap = _try_open(i, backend, name)
            if cap is not None:
                return cap
        # แยกเคส "ไม่มีกล้อง" กับ "มีแต่จอดำ" เพื่อ error message ที่ตรงจุด
        probe = cv2.VideoCapture(i, cv2.CAP_MSMF)
        if probe.isOpened():
            ok, f = probe.read()
            if ok and f is not None:
                saw_black_only = True
        probe.release()

    if saw_black_only:
        raise RuntimeError(
            "กล้องเปิดได้แต่ส่งภาพดำล้วนมาตลอด — เช็คตามลำดับ: "
            "1) จอมือถือติดอยู่และแอป Camo อยู่หน้าสุด "
            "2) Camo Studio บนคอมเห็นภาพสด "
            "3) ปิด-เปิด Camo Studio ใหม่"
        )
    raise RuntimeError(
        "หากล้องไม่เจอ — เช็คว่า Camo/DroidCam ต่ออยู่ แล้วลองตั้ง CAMERA_INDEX ใน config.py"
    )
