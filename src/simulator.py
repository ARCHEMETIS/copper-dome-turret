# =============================================================
# simulator.py — โหมดจำลอง: รันระบบทั้ง loop โดยไม่ต้องมี Arduino/กล้อง
# รัน:  venv\Scripts\python.exe src\main.py --sim
#
# มีอะไรในนี้:
#   SimWorld  : สนามจำลอง — ตุ๊กตา 3 ตัววางสุ่มตำแหน่ง/ระยะ (สุ่มใหม่ทุกนัด
#               ตามโจทย์ "เป้าไม่คงที่")
#   SimTurret : ป้อมเสมือน interface เหมือน hardware.Turret เป๊ะ
#               ตอนยิงจะตัดสินโดน/พลาดจากมุมเล็ง + ระยะตกของลูก แล้วพิมพ์สถิติ
#   SimCamera : กล้องเสมือน — วาดภาพสนามตามมุมป้อมปัจจุบัน (ป้อมหมุน ภาพเลื่อน
#               เหมือนกล้องติดบนป้อมจริง) สีตุ๊กตาตรงกับช่วง HSV ใน config
#
# ประโยชน์: โค้ด aiming/ranging/detector/UI ที่ใช้คือ "ตัวจริง" ทั้งหมด
# วันที่ได้อุปกรณ์ แค่ถอด --sim ออก ระบบที่เหลือผ่านการพิสูจน์แล้ว
# =============================================================
import random
import time

import cv2
import numpy as np

import config

SIM_FOCAL_PX = 900.0                      # focal ของกล้องเสมือน
PX_PER_DEG = config.FRAME_WIDTH / 60.0    # มุมมองภาพ (FOV) ~60°

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
        """สุ่มตำแหน่ง (มุม) และระยะของตุ๊กตาทั้ง 3 — ห่างกันอย่างน้อย 10°"""
        azimuths = random.sample(range(60, 121, 10), 3)
        for label, az in zip(config.TARGETS, azimuths):
            self.targets[label] = {
                "az": az + random.uniform(-3, 3),      # มุมเป้า (หน่วยเดียวกับ pan)
                "dist": random.uniform(1100, 1900),    # อยู่ในช่วงตาราง PWM
            }


class SimTurret:
    """แทน hardware.Turret — เมธอดครบเหมือนกันทุกตัว"""

    def __init__(self, world: SimWorld):
        self.world = world
        self._pan = float(config.PAN_CENTER)
        self.shots = 0
        self.hits = 0

    @property
    def pan_angle(self) -> float:
        return self._pan

    def pan_to(self, angle: float):
        self._pan = max(config.PAN_MIN, min(config.PAN_MAX, angle))

    def pan_by(self, delta_deg: float):
        self.pan_to(self._pan + delta_deg)

    def set_flywheel(self, duty: float):
        pass

    def feed_one(self):
        time.sleep(0.2)

    def fire(self, duty: float):
        time.sleep(0.4)  # แทนเวลา spin-up (ย่อให้เร็วกว่าจริง)

        # ลูก "ตกจริง" ที่ระยะไหน = ตีความตาราง PWM กลับด้าน (สมมติตารางแม่น)
        table = sorted(config.PWM_DISTANCE_TABLE)
        shot_dist = float(np.interp(duty, [p for _, p in table], [d for d, _ in table]))

        # เป้าที่ใกล้แนวเล็งที่สุดคือเป้าที่ลูกพุ่งไปหา
        label, t = min(self.world.targets.items(),
                       key=lambda kv: abs(kv[1]["az"] - self._pan))
        az_err = abs(t["az"] - self._pan)
        dist_err = abs(t["dist"] - shot_dist)

        hit = az_err < 2.0 and dist_err < 150   # เกณฑ์โดน: เล็งเพี้ยน <2° และระยะเพี้ยน <15 cm
        self.shots += 1
        self.hits += hit
        print(f"[SIM] duty={duty:.2f} ลูกตก {shot_dist:.0f} mm | เป้า {label}: "
              f"มุมเพี้ยน {az_err:.1f}° ระยะเพี้ยน {dist_err:.0f} mm → "
              f"{'🎯 โดน!' if hit else '❌ พลาด'}  (สถิติ {self.hits}/{self.shots})")

        self.world.randomize()  # เป้าย้ายที่ทุกนัด — ระบบต้องเล็งใหม่จากศูนย์เสมอ

    def close(self):
        print(f"[SIM] จบ: ยิงโดน {self.hits}/{self.shots}")


class SimCamera:
    """แทน cv2.VideoCapture — วาดภาพสนามตามมุมป้อมปัจจุบัน"""

    def __init__(self, world: SimWorld, turret: SimTurret):
        self.world = world
        self.turret = turret

    def read(self):
        time.sleep(0.02)  # ~50fps กัน loop วิ่งรัว CPU
        w, h = config.FRAME_WIDTH, config.FRAME_HEIGHT
        frame = np.full((h, w, 3), (245, 240, 235), np.uint8)   # พื้นหลังสว่าง
        cv2.rectangle(frame, (0, int(h * 0.72)), (w, h), (200, 150, 80), -1)  # โต๊ะ

        # วาดตัวไกลก่อน (painter's algorithm)
        order = sorted(self.world.targets.items(), key=lambda kv: -kv[1]["dist"])
        for label, t in order:
            # เป้าห่างจากแนวเล็งกี่องศา → กี่ pixel จากกลางภาพ
            dx_px = (t["az"] - self.turret.pan_angle) * PX_PER_DEG
            cx = int(w / 2 + dx_px)
            real_w = config.TARGETS[label]["real_width_mm"]
            w_px = int(SIM_FOCAL_PX * real_w / t["dist"])   # ไกล = เล็ก (สูตรเดียวกับ ranging)
            cy = int(h * 0.72) - int(w_px * 0.6)

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
    """สร้างชุดจำลองครบ + ตั้ง FOCAL_PX ให้ ranging ใช้ได้ทันที"""
    config.FOCAL_PX = SIM_FOCAL_PX
    world = SimWorld()
    turret = SimTurret(world)
    camera = SimCamera(world, turret)
    return camera, turret
