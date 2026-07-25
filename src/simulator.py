# =============================================================
# simulator.py — โหมดจำลอง: รันระบบทั้ง loop โดยไม่ต้องมี Arduino/กล้อง
# รัน:  venv\Scripts\python.exe src\main.py --sim
#
# มีอะไรในนี้:
#   SimWorld  : สนามจำลอง — ตุ๊กตา 3 ตัววางสุ่มตำแหน่ง/ระยะ (สุ่มใหม่ทุกนัด
#               ตามโจทย์ "เป้าไม่คงที่") ทุกตัวอยู่บนโต๊ะสูงกว่าปากกระบอก
#               → แต่ละตัวมีมุมเงย (el) ของตัวเองตามระยะ
#   SimTurret : ป้อมเสมือน interface เหมือน hardware.Turret เป๊ะ (pan + tilt)
#               ตอนยิงตัดสินโดน/พลาดจาก error การเล็งทั้งสองแกน แล้วพิมพ์สถิติ
#   SimCamera : กล้องเสมือน "ติดลำกล้อง" (โหมดสโคป) — ภาพเลื่อนทั้งแนวนอนตาม
#               pan และแนวตั้งตาม tilt เหมือนกล้องจริงที่ขันติดกับตัวยิง
#
# ประโยชน์: โค้ด aiming/detector/UI ที่ใช้คือ "ตัวจริง" ทั้งหมด
# วันที่ได้อุปกรณ์ แค่ถอด --sim ออก ระบบที่เหลือผ่านการพิสูจน์แล้ว
# =============================================================
import math
import random
import time

import cv2
import numpy as np

import config

SIM_FOCAL_PX = 900.0                      # focal ของกล้องเสมือน
PX_PER_DEG = config.FRAME_WIDTH / 60.0    # มุมมองภาพ (FOV) ~60°
SIM_TARGET_RAISE_MM = 350.0               # เป้าอยู่สูงกว่าปากกระบอกเท่านี้ (โต๊ะ 800 - ฐานปืน ~450)

_COLORS = {                                # BGR ที่ตกในช่วง HSV ของ config พอดี
    "dino": (0, 200, 0),                   # เขียวสด
    "capybara": (40, 80, 160),             # น้ำตาล
    "elephant": (120, 120, 120),           # เทา
}


class SimWorld:
    def __init__(self):
        self.targets = {}
        self.randomize()

    def randomize(self):
        """สุ่มตำแหน่ง (มุม) และระยะของตุ๊กตาทั้ง 3 — ห่างกันอย่างน้อย 10°
        el = มุมเงยที่ต้องชี้ถึงจะโดน (ทุกตัวสูงเท่ากัน ต่างที่ระยะ → el ต่างกันเล็กน้อย)"""
        azimuths = random.sample(range(60, 121, 10), 3)
        for label, az in zip(config.TARGETS, azimuths):
            dist = random.uniform(1500, 2400)          # ช่วงสนามจริง
            self.targets[label] = {
                "az": az + random.uniform(-3, 3),      # มุมเป้า (หน่วยเดียวกับ pan)
                "dist": dist,
                "el": math.degrees(math.atan2(SIM_TARGET_RAISE_MM, dist)),
            }


class SimTurret:
    """แทน hardware.Turret — เมธอดครบเหมือนกันทุกตัว

    ⚠ มุม servo กับทิศจริงของลำกล้อง "กลับด้านกัน" (25 ก.ค.) — เฟืองบนป้อมจริง
    ต่อแบบมิเรอร์ทั้งสองแกน คาลิเบรตไว้ใน config เป็น AIM_SIGN/AIM_TILT_SIGN = -1
    (24 ก.ค.) แต่ sim เดิมยังเป็นป้อมอุดมคติ "มุมเพิ่ม = ขวา/ขึ้น" → ลูปเล็งวิ่งหนีเป้า
    ทั้งสองแกน smoke test ตกทั้ง 9 นัด

    เลิกใช้ _pan/_tilt (มุม servo) คิดเรื่องทิศโดยตรง ให้ผ่าน yaw/pitch เสมอ:
        servo pan เพิ่ม  → ลำกล้องหันซ้าย  (yaw ลด)
        servo tilt เพิ่ม → ลำกล้องก้มลง    (pitch ลด, 180° = แนวระนาบ)
    """

    def __init__(self, world: SimWorld):
        self.world = world
        self._pan = float(config.PAN_CENTER)
        self._tilt = float(config.TILT_CENTER)
        self.shots = 0
        self.hits = 0

    @property
    def pan_angle(self) -> float:
        return self._pan

    def pan_to(self, angle: float):
        self._pan = max(config.PAN_MIN, min(config.PAN_MAX, angle))

    def pan_by(self, delta_deg: float):
        self.pan_to(self._pan + delta_deg)

    @property
    def tilt_angle(self) -> float:
        return self._tilt

    def tilt_to(self, angle: float):
        self._tilt = max(config.TILT_MIN, min(config.TILT_MAX, angle))

    def tilt_by(self, delta_deg: float):
        self.tilt_to(self._tilt + delta_deg)

    @property
    def yaw(self) -> float:
        """ทิศจริงที่ลำกล้องชี้ (หน่วยเดียวกับ az ของเป้า) — มิเรอร์จากมุม servo"""
        return 2 * config.PAN_CENTER - self._pan

    @property
    def pitch(self) -> float:
        """มุมลำกล้องเหนือระนาบ (องศา) — มิเรอร์จากมุม servo เช่นกัน"""
        return config.TILT_CENTER - self._tilt

    def fire(self):
        time.sleep(0.4)  # แทนเวลาดึง+ปล่อยเฟือง (ย่อให้เร็วกว่าจริง)

        # โหมดสโคป ยิงแรงคงที่วิถีแบน — โดน/พลาดตัดสินจาก error การเล็งล้วนๆ
        # เป้าที่ใกล้แนวเล็งที่สุดคือเป้าที่ลูกพุ่งไปหา
        label, t = min(self.world.targets.items(),
                       key=lambda kv: abs(kv[1]["az"] - self.yaw))
        az_err = abs(t["az"] - self.yaw)
        el_err = abs(t["el"] - self.pitch)

        hit = az_err < 2.0 and el_err < 2.0   # เกณฑ์โดน: เล็งเพี้ยนไม่เกิน 2° ทั้งสองแกน
        self.shots += 1
        self.hits += hit
        print(f"[SIM] yaw={self.yaw:.1f}° pitch={self.pitch:.1f}° | เป้า {label} "
              f"@{t['dist']:.0f}mm: มุมเพี้ยน H {az_err:.1f}° V {el_err:.1f}° → "
              f"{'🎯 โดน!' if hit else '❌ พลาด'}  (สถิติ {self.hits}/{self.shots})")

        self.world.randomize()  # เป้าย้ายที่ทุกนัด — ระบบต้องเล็งใหม่จากศูนย์เสมอ

    def close(self):
        print(f"[SIM] จบ: ยิงโดน {self.hits}/{self.shots}")


class SimCamera:
    """แทน cv2.VideoCapture — กล้องติดลำกล้อง: ภาพเลื่อนตามทั้ง pan และ tilt"""

    def __init__(self, world: SimWorld, turret: SimTurret):
        self.world = world
        self.turret = turret

    def read(self):
        time.sleep(0.02)  # ~50fps กัน loop วิ่งรัว CPU
        w, h = config.FRAME_WIDTH, config.FRAME_HEIGHT
        frame = np.full((h, w, 3), (245, 240, 235), np.uint8)   # พื้นหลังสว่าง

        pitch = self.turret.pitch
        # โต๊ะ (คร่าวๆ ไว้เป็นฉากหลัง): ขอบบนโต๊ะอยู่แนวระนาบ → เลื่อนลงเมื่อเงยขึ้น
        table_top = int(h / 2 + pitch * PX_PER_DEG)
        if table_top < h:
            cv2.rectangle(frame, (0, max(0, table_top)), (w, h), (200, 150, 80), -1)

        # วาดตัวไกลก่อน (painter's algorithm)
        order = sorted(self.world.targets.items(), key=lambda kv: -kv[1]["dist"])
        for label, t in order:
            # แนวนอน: เป้าห่างจากแนวเล็งกี่องศา → กี่ pixel จากกลางภาพ
            dx_px = (t["az"] - self.turret.yaw) * PX_PER_DEG
            cx = int(w / 2 + dx_px)
            # แนวตั้ง: เป้าสูงกว่าแนวลำกล้องกี่องศา → เหนือ/ใต้กลางภาพ
            dy_px = (t["el"] - pitch) * PX_PER_DEG
            cy = int(h / 2 - dy_px)
            real_w = config.TARGETS[label]["real_width_mm"]
            w_px = int(SIM_FOCAL_PX * real_w / t["dist"])   # ไกล = เล็ก (สูตรเดียวกับ ranging)

            color = _COLORS[label]
            cv2.ellipse(frame, (cx, cy), (w_px // 2, int(w_px * 0.6)),
                        0, 0, 360, color, -1)                          # ตัว
            # หัวต้องไม่ยื่นพ้นความกว้างลำตัว — ไม่งั้นกรอบ detect กว้างกว่า
            # real_width แล้วระยะที่วัดจะเพี้ยน (บั๊กที่เจอจริงจาก smoke test!)
            cv2.circle(frame, (cx + w_px // 3, cy - int(w_px * 0.45)),
                       w_px // 6, color, -1)                           # หัว
        return True, frame

    def release(self):
        pass


def create_sim():
    """สร้างชุดจำลองครบ + ตั้ง FOCAL_PX/real_size_mm ให้ ranging ใช้ได้ทันที"""
    config.FOCAL_PX = SIM_FOCAL_PX
    # ranging ใช้ √(w·h) ของกรอบ — รูปที่ซิมวาด (ตัวรี 1.2·w + หัวโผล่นิดหน่อย)
    # มีกรอบสูง ≈ 1.217 เท่าของความกว้าง → ขนาดผลจริงของเป้าจำลอง
    # = real_width_mm · √1.217 ≈ ×1.103 (ถ้าแก้รูปทรงที่วาดใน SimCamera.read
    # ต้องอัพเดตตัวคูณนี้ด้วย — smoke test จะจับได้ถ้าลืม)
    for t in config.TARGETS.values():
        t["real_size_mm"] = t["real_width_mm"] * 1.103
    # ตัวแก้ระยะตามท่า (w/h) fit มาจากตุ๊กตาจริง — เป้าจำลองมีรูปทรงเดียวตายตัว
    # (w/h ≈ 0.82 ทุกตัว) ไม่มี "ท่า" ให้แก้ ถ้าปล่อยไว้จะโดนคูณ factor ของท่า
    # ที่ไม่ได้เป็น ทำระยะใน sim เพี้ยน ~10% ทั้งที่โค้ดถูก (smoke test เคยจับได้)
    config.ASPECT_CORRECTION = {}
    world = SimWorld()
    turret = SimTurret(world)
    camera = SimCamera(world, turret)
    return camera, turret
