# =============================================================
# config.py — ค่าคงที่ทั้งหมดของระบบ รวมไว้ที่เดียว
# กติกา: ไฟล์อื่นห้าม hardcode ตัวเลข ให้ import จากที่นี่เท่านั้น
# ค่าที่ขึ้นต้นด้วย TODO ต้องวัด/จูนจากของจริงก่อนใช้
# =============================================================
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ---------- Serial / Arduino ----------
SERIAL_PORT = None          # None = ค้นหาอัตโนมัติ, หรือระบุเอง เช่น "COM4"
                            # ดูพอร์ตได้ใน Device Manager > Ports (COM & LPT)

# ---------- ขา Arduino (Uno + Sensor Shield v5) ----------
PIN_PAN_SERVO = 9           # MG945 หมุนป้อม
PIN_FEEDER_SERVO = 10       # MG945 ดันลูก
PIN_FLYWHEEL_ENA = 5        # PWM -> ENA ของ L298N (มอเตอร์ล้อซ้าย)
PIN_FLYWHEEL_ENB = 6        # PWM -> ENB ของ L298N (มอเตอร์ล้อขวา)
PIN_IN1 = 2                 # ทิศทางมอเตอร์ A (ตั้งครั้งเดียวตอนเปิดเครื่อง)
PIN_IN2 = 4
PIN_IN3 = 7
PIN_IN4 = 8
# หมายเหตุ: ล้อสองข้างต้องหมุน "สวนทางกัน" เพื่อหนีบลูกพุ่งไปข้างหน้า
# ถ้าลูกไม่พุ่ง ให้สลับค่า IN ในคู่ใดคู่หนึ่ง (ดู hardware.py)

# ---------- Servo: ขอบเขตมุม ----------
PAN_CENTER = 90
PAN_MIN = 40                # กันสายพันคอป้อม (แผนคือ ±40°)
PAN_MAX = 140
FEEDER_REST = 20            # TODO: มุมพัก (ลูกยังไม่เข้าล้อ) — จูนจากของจริง
FEEDER_PUSH = 100           # TODO: มุมดันลูกเข้าล้อ — จูนจากของจริง
FEEDER_PUSH_TIME_S = 0.35   # เวลาค้างตอนดัน
FEEDER_RETURN_TIME_S = 0.4  # เวลารอ servo กลับที่พัก

# ---------- Flywheel ----------
FLYWHEEL_SPINUP_S = 1.2     # รอล้อหมุนเต็มรอบก่อนป้อนลูก
FLYWHEEL_MIN_DUTY = 0.35    # ต่ำกว่านี้ล้อมักไม่หมุน (แรงเสียดทาน) TODO: วัดจริง
FLYWHEEL_MAX_DUTY = 1.0

# ตาราง calibration: (ระยะ_mm, duty 0..1) — ได้จาก tools/calibrate_pwm.py
# เรียงจากใกล้ไปไกล ระบบจะ interpolate ระหว่างจุดให้เอง
# TODO: ค่าข้างล่างเป็น placeholder ห้ามใช้จริงจนกว่าจะยิงวัดเอง!
PWM_DISTANCE_TABLE = [
    (1000, 0.45),
    (1500, 0.60),
    (2000, 0.80),
]

# ---------- กล้อง ----------
CAMERA_INDEX = 1            # 1 = Camo (มือถือ) | 0 = กล้องโน้ตบุ๊ก | None = ไล่หาอัตโนมัติ
FRAME_WIDTH = 1280
FRAME_HEIGHT = 720

# focal length เป็น pixel — ได้จาก tools/calibrate_focal.py
# สูตร: ระยะ_mm = FOCAL_PX * ขนาดจริง_mm / ขนาดใน_ภาพ_px
FOCAL_PX = None             # TODO: calibrate ก่อน (ล็อก focus มือถือแล้วห้ามแตะอีก!)

# ---------- เป้า 3 ตัว ----------
# real_width_mm = ความกว้างจริงของตุ๊กตา (วัดด้วยไม้บรรทัด แนวเดียวกับที่กล้องเห็น)
TARGETS = {
    "dino": {
        "display": "ไดโนเสาร์เขียว",
        "real_width_mm": 100,          # TODO: วัดจริง
        "yolo_class": 1,               # ตรงกับลำดับ class ตอนเทรน YOLO (data.yaml: capybara,dino,elephant)
        "hsv_lower": (35, 80, 60),     # ช่วงสีเขียว (สำรอง ถ้า YOLO ไม่ทัน)
        "hsv_upper": (85, 255, 255),
    },
    "capybara": {
        "display": "คาปิบาร่า",
        "real_width_mm": 100,          # TODO: วัดจริง
        "yolo_class": 0,
        "hsv_lower": (10, 60, 60),     # น้ำตาล — เสี่ยงชนกับช้าง ควรใช้ YOLO
        "hsv_upper": (25, 255, 255),
    },
    "elephant": {
        "display": "ช้างเทา",
        "real_width_mm": 100,          # TODO: วัดจริง
        "yolo_class": 2,
        "hsv_lower": (0, 0, 40),       # เทา — HSV แยกยากมาก ควรใช้ YOLO
        "hsv_upper": (180, 40, 200),
    },
}

# ---------- Vision ----------
DETECTOR = "yolo"           # "yolo" หรือ "hsv" — เทรน YOLO เสร็จแล้ว (mAP50 0.971)
# ผูกกับตำแหน่งโปรเจคเสมอ (ไม่ใช่ cwd) — ไม่งั้นรันจากโฟลเดอร์อื่นแล้วหาไฟล์ไม่เจอ
YOLO_MODEL_PATH = str(_PROJECT_ROOT / "models" / "best.pt")
YOLO_CONF = 0.5
HSV_MIN_AREA_PX = 800       # กรอง noise เล็กๆ ทิ้ง

# ---------- Visual servoing (การเล็ง) ----------
AIM_DEADBAND_PX = 15        # เป้าห่างกลางภาพไม่เกินนี้ = ถือว่าเล็งตรงแล้ว
AIM_KP = 0.03               # องศาที่หมุนต่อ 1 pixel ของ error (จูนถ้าส่าย/ช้าไป)
AIM_MAX_STEP_DEG = 6        # หมุนทีละไม่เกินกี่องศา (กันเหวี่ยงเกิน)
AIM_SETTLE_S = 0.20         # รอป้อม+ภาพนิ่งหลังหมุนแต่ละครั้ง
AIM_CONFIRM_FRAMES = 3      # ต้องอยู่กลางภาพติดกันกี่เฟรมถึงยอมยิง
AIM_TIMEOUT_S = 12          # หาเป้าไม่เจอ/เล็งไม่เข้าภายในเวลานี้ = ยกเลิก
AIM_SIGN = +1               # ถ้าป้อมหมุน "หนี" เป้าแทนที่จะเข้าหา ให้เปลี่ยนเป็น -1
