# =============================================================
# compare_aiming.py — เปรียบเทียบ 3 แบบการวางกล้อง ด้วย Monte Carlo 10,000 นัด
# รัน:  venv\Scripts\python.exe tools\compare_aiming.py
#
#   A) กล้องบนป้อม (closed-loop):  กล้องเห็น error ที่เหลือ → หมุนแก้จนต่ำกว่า
#      deadband ความเพี้ยนของ servo ถูกหักล้างด้วย feedback
#   B) กล้อง fix บนเสาเหนือแกนหมุน (open-loop):  คำนวณมุมครั้งเดียวแล้วสั่ง
#      ไม่มี feedback — โดน slop/quantization/calibration เต็มๆ แต่ไม่มี parallax
#   C) กล้อง fix ข้างป้อม (open-loop + parallax):  เหมือน B แต่ต้องแก้ parallax
#      ด้วยระยะที่วัดได้ → ความเพี้ยนของการวัดระยะรั่วเข้ามาเป็นความเพี้ยนมุมด้วย
#
# ⚠️ ผลลัพธ์ขึ้นกับสมมติฐานด้านล่างทั้งหมด — ไม่เห็นด้วยตัวไหน แก้เลขแล้วรันใหม่!
# ตัวแปรชี้ขาดคือ SERVO_SLOP_DEG: "วัดจริงได้" ตั้งแต่วันแรกที่ได้ servo
# (สั่งไป 90° → 100° → 90° หลายรอบ วัดว่าหัวชี้ที่เดิมเป๊ะแค่ไหน)
# =============================================================
import math
import random

random.seed(42)              # ให้ผลซ้ำได้ทุกครั้งที่รัน (คุยกันบนตัวเลขชุดเดียวกัน)
N = 10_000                   # จำนวนนัดที่จำลองต่อแบบ

# ---------- สมมติฐาน (แก้เลขพวกนี้ได้เลย) ----------
DIST_MIN, DIST_MAX = 1100, 1900   # ระยะเป้า (mm) ตามสนามจริง ~1.5 m ± ช่วงวาง
TARGET_HALF_W = 50                # ครึ่งความกว้างตุ๊กตา (mm) — โดนถ้าพลาดไม่เกินนี้

SERVO_QUANT_DEG = 1.0             # Firmata สั่ง servo เป็นจำนวนเต็มองศา (ปัดเศษ)
SERVO_SLOP_DEG = 1.5              # ← ตัวชี้ขาด! backlash เฟือง MG945 (±) วัดจริงได้
SERVO_REPEAT_DEG = 0.3            # ความไม่ซ้ำของ servo แม้สั่งมุมเดิม (±)

DEADBAND_DEG = 0.7                # closed-loop: 15px ≈ 0.7° ที่ FOV 60°/1280px
RECOIL_DRIFT_DEG = 0.3            # ป้อมขยับเล็กน้อยช่วงยืนยันเป้า→ลูกออกจริง (±)

CALIB_ERR_DEG = 0.8               # open-loop: ความเพี้ยนของตาราง pixel→มุม (±)
CAM_OFFSET_MM = 200               # แบบ C: กล้องอยู่ห่างแกนหมุนไปด้านข้างกี่ mm
RANGE_ERR_PCT = 0.08              # วัดระยะเพี้ยน ±8% (monocular ranging ทั่วไป)

u = random.uniform


def hit(err_deg: float, dist: float) -> bool:
    """พลาดเชิงมุม err_deg ที่ระยะ dist แล้วยังโดนตัวตุ๊กตาไหม"""
    return abs(math.tan(math.radians(err_deg))) * dist < TARGET_HALF_W


def shot_closed_loop(dist: float) -> float:
    # feedback ไล่แก้จน error < deadband — ความเพี้ยน servo ถูกกลืนใน loop
    residual = u(-DEADBAND_DEG, DEADBAND_DEG)
    return residual + u(-RECOIL_DRIFT_DEG, RECOIL_DRIFT_DEG)


def shot_open_loop(dist: float, parallax: bool, slop: float = SERVO_SLOP_DEG) -> float:
    err = u(-CALIB_ERR_DEG, CALIB_ERR_DEG)                 # ตาราง pixel→มุมไม่เป๊ะ
    cmd_true = err                                          # มุมที่ "ควรสั่ง" + เพี้ยน calib
    quantized = round(cmd_true / SERVO_QUANT_DEG) * SERVO_QUANT_DEG
    err += (quantized - cmd_true)                           # ปัดเศษเป็นจำนวนเต็มองศา
    err += u(-slop, slop)                                   # backlash — ไม่มีใครมาแก้ให้
    err += u(-SERVO_REPEAT_DEG, SERVO_REPEAT_DEG)
    if parallax:
        # ต้องแก้ parallax ด้วยระยะที่ "วัดได้" ซึ่งเพี้ยนจากระยะจริง
        dist_meas = dist * (1 + u(-RANGE_ERR_PCT, RANGE_ERR_PCT))
        corr_true = math.degrees(math.atan(CAM_OFFSET_MM / dist))
        corr_used = math.degrees(math.atan(CAM_OFFSET_MM / dist_meas))
        err += corr_used - corr_true
    return err


def run(label: str, fn) -> None:
    hits = sum(hit(fn(d := u(DIST_MIN, DIST_MAX)), d) for _ in range(N))
    pct = 100 * hits / N
    bar = "█" * int(pct / 2.5)
    print(f"  {label:<44} {pct:5.1f}%  {bar}")


print(f"จำลอง {N:,} นัด/แบบ | เป้ากว้าง ±{TARGET_HALF_W} mm ที่ระยะ {DIST_MIN}-{DIST_MAX} mm")
print(f"servo: slop ±{SERVO_SLOP_DEG}° quant {SERVO_QUANT_DEG}° | calib ±{CALIB_ERR_DEG}° | วัดระยะ ±{RANGE_ERR_PCT:.0%}\n")
print("อัตรา 'เล็งโดนตัว' (เฉพาะแกนซ้าย-ขวา ยังไม่รวมความเพี้ยนระยะยิงซึ่งโดนทุกแบบเท่ากัน):")
run("A) กล้องบนป้อม (closed-loop)", shot_closed_loop)
run("B) กล้อง fix เหนือแกนหมุน (open-loop)", lambda d: shot_open_loop(d, parallax=False))
run(f"C) กล้อง fix ข้างป้อม {CAM_OFFSET_MM} mm (open+parallax)", lambda d: shot_open_loop(d, parallax=True))

# มุมพลาดสูงสุดที่ยังโดน ณ ระยะไกลสุด = งบความเพี้ยนรวมที่ open-loop มีให้ใช้
budget = math.degrees(math.atan(TARGET_HALF_W / DIST_MAX))
worst_open = CALIB_ERR_DEG + SERVO_QUANT_DEG / 2 + SERVO_SLOP_DEG + SERVO_REPEAT_DEG
print(f"""
เกณฑ์ตัดสินแบบวิศวกร (ไม่ต้องเชื่อใคร — วัดเอา):
  ที่ระยะไกลสุด {DIST_MAX} mm งบความเพี้ยนมุมรวม = ±{budget:.2f}°
  open-loop กรณีแย่สุดตามสมมติฐานนี้  = ±{worst_open:.2f}°  {'≤ งบ ✓ ไปต่อได้' if worst_open <= budget else '> งบ ✗ เกินงบ'}
  → วันแรกที่ได้ servo: วัด slop จริง (สั่ง 90→100→90 ซ้ำๆ ดูว่านิ่งแค่ไหน)
    ถ้า slop จริง + calib ต่ำกว่างบ → แบบ fix ของเพื่อนใช้ได้จริง ไม่ต้องเถียงกัน
    ถ้าเกินงบ → ต้องมี feedback (กล้องบนป้อม) ตัวเลขตัดสินให้เอง
""")

print("ความไวต่อ slop ของ servo (แบบ B open-loop — closed-loop อยู่ ~100% ตลอดช่วง):")
for slop in (0.5, 1.0, 1.5, 2.0, 2.5, 3.0):
    hits = sum(hit(shot_open_loop(d := u(DIST_MIN, DIST_MAX), False, slop), d)
               for _ in range(N))
    pct = 100 * hits / N
    print(f"  slop ±{slop}°  →  เล็งโดน {pct:5.1f}%  {'█' * int(pct / 2.5)}")
print("\n  MG945 ของแท้มัก ±1° แต่ของ clone เจอ ±2-3° บ่อย → วัดของจริงเท่านั้นถึงรู้")
