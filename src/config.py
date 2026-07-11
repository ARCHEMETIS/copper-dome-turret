# =============================================================
# config.py — ค่าคงที่ทั้งหมดของระบบ รวมไว้ที่เดียว
# กติกา: ไฟล์อื่นห้าม hardcode ตัวเลข ให้ import จากที่นี่เท่านั้น
# ค่าที่ขึ้นต้นด้วย TODO ต้องวัด/จูนจากของจริงก่อนใช้
# =============================================================
import hashlib
from functools import lru_cache
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

# focal length เป็น pixel — fit จากรูปชุด Distance/ ด้วย tools/fit_focal.py
# สูตร: ระยะ_mm = FOCAL_PX * ขนาดจริง_mm / ขนาดใน_ภาพ_px
# ⚠ ค่านี้สเกลมาจากรูปโหมดถ่ายภาพ iPhone (4064px → 1280px) — FOV โหมดรูปกับ
# โหมดวิดีโอ Camo อาจไม่เท่ากัน TODO: ถ่ายผ่าน Camo ที่ระยะที่รู้ 1-2 รูปเพื่อยืนยัน
# (ล็อก focus/zoom มือถือแล้วห้ามแตะอีก ไม่งั้นค่านี้เพี้ยนทั้งระบบ!)
FOCAL_PX = 1400

# ---------- เป้า 3 ตัว ----------
# real_size_mm = ขนาด "ผลจริง" √(กว้าง·สูง) ที่กรอบ YOLO เห็น — fit จากรูปชุด
# Distance/ ด้วย tools/fit_focal.py — ranging ใช้ค่านี้ (√(w·h) ทนท่าวางแปลกๆ
# วันแข่งได้ดีสุด: หมุนตุ๊กตาแล้ว w↔h สลับกันแต่ √(w·h) แทบไม่เปลี่ยน)
# real_width_mm = ความกว้างผลจริง (fit เช่นกัน) — เหลือไว้ให้ simulator วาดเป้า
# ค่าพวกนี้ยังใช้ได้แม้ FOCAL_PX จะถูกปรับตอนยืนยันผ่าน Camo
# (FOV เปลี่ยน = px ทุกอย่างสเกลเท่ากัน แก้ที่ FOCAL_PX ตัวเดียวพอ)
# คาลิเบรตกับโมเดลรอบ 3 แล้ว (10 ก.ค. — Distance/ranging_log.csv 42 แถว:
# 2 ระยะ 100/175cm × 7 ท่า × 3 ตัว, median ของขนาดโดยนัย size_px·dist/FOCAL)
# ความสอดคล้องข้ามระยะดีมาก (ต่างกัน <2%) = ยืนยัน FOCAL_PX 1400 ไปในตัว
# ⚠ ถ้าเทรนโมเดลใหม่อีกรอบ ต้องเก็บซ้ำด้วย tools/collect_ranging_data.py
TARGETS = {
    "dino": {
        "display": "ไดโนเสาร์เขียว",
        "real_size_mm": 171,           # median 14 จุด 2 ระยะ×7 ท่า (ranging_log.csv)
        "real_width_mm": 145,
        "yolo_class": 1,               # ตรงกับลำดับ class ตอนเทรน YOLO (data.yaml: capybara,dino,elephant)
        "hsv_lower": (35, 80, 60),     # ช่วงสีเขียว (สำรอง ถ้า YOLO ไม่ทัน)
        "hsv_upper": (85, 255, 255),
    },
    "capybara": {
        "display": "คาปิบาร่า",
        "real_size_mm": 138,           # median 14 จุด 2 ระยะ×7 ท่า (ranging_log.csv)
        "real_width_mm": 118,
        "yolo_class": 0,
        "hsv_lower": (10, 60, 60),     # น้ำตาล — เสี่ยงชนกับช้าง ควรใช้ YOLO
        "hsv_upper": (25, 255, 255),
    },
    "elephant": {
        "display": "ช้างเทา",
        "real_size_mm": 161,           # median 14 จุด 2 ระยะ×7 ท่า (ranging_log.csv)
        "real_width_mm": 185,
        "yolo_class": 2,
        "hsv_lower": (0, 0, 40),       # เทา — HSV แยกยากมาก ควรใช้ YOLO
        "hsv_upper": (180, 40, 200),
    },
}

# ตัวแก้ระยะตามท่า (ranging.py ใช้): {toy: [(aspect, factor), ...]} = จุด knot
# aspect = w/h ของกรอบ YOLO — บอก "ท่า" ได้: เช่น dino ยืนตรง w/h~0.65,
# หันข้าง ~1.0 (เงาใหญ่ อ่านใกล้เกิน -20% → คูณ ~1.25 ชดเชย)
# ranging ใช้ np.interp ระหว่าง knot จึงต่อเนื่อง — เดิมเป็นแถบ w/h ตายตัว
# ซึ่งมีหน้าผาตรงขอบแถบ (factor กระโดด 14-24%) ทั้งที่ข้อมูลจริงมีจุดนั่ง
# ห่างขอบแค่ ~3% = กรอบสั่นไม่กี่ px ตอนยิงจริงก็ข้ามแถบ ระยะเด้งทั้งนัด
# fit จาก Distance/ranging_log.csv ด้วย tools/fit_aspect.py (โมเดลรอบ 3, 42 จุด)
# หลังแก้: แย่สุด ±10.6% จากเดิม ±21.9% — ตัวเลข in-sample! เช็คของจริงด้วย
# tools/collect_ranging_data.py ที่ระยะที่สาม (ที่ไม่ได้ใช้ fit) ก่อนเชื่อสนิท
# ⚠ ผูกกับโมเดล+ตุ๊กตาชุดนี้ ถ้าเทรนใหม่/เปลี่ยนตุ๊กตา ต้อง fit ใหม่พร้อม real_size_mm
ASPECT_CORRECTION = {
    "capybara": [(0.771, 1.008), (0.83, 1.057), (0.995, 0.89), (1.061, 0.872)],
    "dino": [(0.646, 1.009), (0.765, 0.899), (1.0, 1.251), (1.164, 0.933),
             (1.382, 0.98)],
    "elephant": [(0.905, 1.021), (0.989, 1.067), (1.076, 0.867), (1.13, 0.928),
                 (1.335, 0.863), (1.448, 0.917)],
}

# ---------- Vision ----------
DETECTOR = "yolo"           # "yolo" หรือ "hsv" — YOLO เทรนรอบ 3 แล้ว (mAP50 0.963 valid / 0.965 test + ลด ghost ด้วย background 138 รูป)
# ผูกกับตำแหน่งโปรเจคเสมอ (ไม่ใช่ cwd) — ไม่งั้นรันจากโฟลเดอร์อื่นแล้วหาไฟล์ไม่เจอ
YOLO_MODEL_PATH = str(_PROJECT_ROOT / "models" / "best.pt")


@lru_cache(maxsize=1)
def yolo_model_tag() -> str:
    """ป้ายประจำไฟล์โมเดล = ชื่อ + hash สั้น เช่น "best.pt@1a2b3c4d"
    ใช้แท็กแถวใน Distance/ranging_log.csv — ชื่อไฟล์เฉยๆ แยกโมเดลไม่ได้
    เพราะเทรนกี่รอบก็ copy ทับมาเป็น best.pt เหมือนกันหมด แต่ข้อมูล ranging
    ข้ามโมเดลปนกันไม่ได้ (นิสัยการตีกรอบของแต่ละโมเดลไม่เหมือนกัน)"""
    p = Path(YOLO_MODEL_PATH)
    return f"{p.name}@{hashlib.sha1(p.read_bytes()).hexdigest()[:8]}"
YOLO_CONF = 0.5             # ⚠ อย่าขึ้นทั้งระบบเพื่อฆ่า ghost — ตุ๊กตาท่ายาก conf ต่ำจริง
                            # (test set: capybara p5=0.26, dino p5=0.53) ให้ประตูข้างล่างจัดการแทน
HSV_MIN_AREA_PX = 800       # กรอง noise เล็กๆ ทิ้ง

# ---------- ประตูกัน ghost (เฉพาะ YoloDetector — HSV/sim ไม่เกี่ยว) ----------
# หลักฐาน+เหตุผลอยู่ docs/vision-baseline.md ข้อ 4 และ wayfinder #10:
# ghost บนคลิป negative อยู่ทนสุด 233ms แต่ตุ๊กตาจริงเจอ 96% ของเฟรม
GATE_PERSIST_FRAMES = 3         # เห็นสะสมกี่เฟรม (นับ +1/-1) ก่อนยอมปล่อย detection
GATE_DIST_RANGE_MM = (500, 4500)  # ระยะที่เป็นไปได้ → ขอบเขตขนาดกรอบผ่านสูตร ranging
                                  # (ขอบไกล 4.5m: เคยตั้ง 3.5m แล้วตาบอดใส่ capybara
                                  # ตัวจริงใน VideoForTest ที่ ~4m — สนามจริง 1.5-2.4m
                                  # แต่ตอนซ้อม/กวาดหาเป้า เจอไกลกว่านั้นได้จริง)

# ---------- Visual servoing (การเล็ง) ----------
AIM_DEADBAND_PX = 15        # เป้าห่างกลางภาพไม่เกินนี้ = ถือว่าเล็งตรงแล้ว
AIM_KP = 0.03               # องศาที่หมุนต่อ 1 pixel ของ error (จูนถ้าส่าย/ช้าไป)
AIM_MAX_STEP_DEG = 6        # หมุนทีละไม่เกินกี่องศา (กันเหวี่ยงเกิน)
AIM_SETTLE_S = 0.20         # รอป้อม+ภาพนิ่งหลังหมุนแต่ละครั้ง
AIM_CONFIRM_FRAMES = 3      # ต้องอยู่กลางภาพติดกันกี่เฟรมถึงยอมยิง
AIM_TIMEOUT_S = 12          # หาเป้าไม่เจอ/เล็งไม่เข้าภายในเวลานี้ = ยกเลิก
AIM_SIGN = +1               # ถ้าป้อมหมุน "หนี" เป้าแทนที่จะเข้าหา ให้เปลี่ยนเป็น -1
