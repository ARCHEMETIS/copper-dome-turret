# =============================================================
# camera.py — เปิดกล้อง (มือถือผ่าน Camo/DroidCam จะโผล่เป็น webcam ปกติ)
# =============================================================
import cv2

import config


def open_camera() -> cv2.VideoCapture:
    """เปิดกล้องตาม config ถ้าไม่ระบุ index จะไล่หา 0-5 ให้เอง"""
    indexes = [config.CAMERA_INDEX] if config.CAMERA_INDEX is not None else range(6)
    for i in indexes:
        # CAP_DSHOW ทำให้เปิดเร็วขึ้นบน Windows และลดปัญหากับกล้องเสมือน
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if cap.isOpened():
            ok, _ = cap.read()
            if ok:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.FRAME_WIDTH)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_HEIGHT)
                print(f"[camera] เปิดกล้อง index {i} สำเร็จ")
                return cap
        cap.release()
    raise RuntimeError(
        "หากล้องไม่เจอ — เช็คว่า Camo/DroidCam ต่ออยู่ แล้วลองตั้ง CAMERA_INDEX ใน config.py"
    )
