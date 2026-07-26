# =============================================================
# manual_aim.py — จอเล็งแบบ "ขยับเอง" (กล้องจริง + Arduino จริง)
# ⚠ รันไฟล์นี้ก่อน main_click.py เสมอในวันจูน
#
# ทำไมต้องมี: `test_hardware.py` มีปุ่มขยับป้อมแต่ไม่มีภาพ, `main_click.py` มีภาพ
# แต่ขยับเองไม่ได้ (ป้อมหันอัตโนมัติ) — การจูน `AIM_SIGN`/`AIM_TILT_SIGN` ต้องการ
# ทั้งสองอย่างพร้อมกัน: สั่งหมุนทีละนิดแล้ว "ดูว่าภาพเลื่อนไปทางไหน"
# ถ้าปล่อยออโต้ทั้งที่ทิศยังผิด ป้อมจะหมุนหนีเป้าไปชนลิมิต — เสียเวลาและเสี่ยงกลไก
#
# รัน: venv\Scripts\python.exe tools\manual_aim.py
#      ใส่ --no-detect ถ้าไม่อยากให้ YOLO ทำงาน (เบาเครื่อง ดูภาพดิบ)
#
# ⚠ ข้อความบนจอเป็นภาษาอังกฤษล้วน — cv2.putText ใช้ฟอนต์ Hershey ที่มีแต่ ASCII
#   วาดภาษาไทยออกมาเป็นกล่องว่าง (เคยเจอตอนทำ collect_ranging_data.py ซึ่งแก้ด้วย
#   Pillow+Leelawadee) ที่นี่เลี่ยงปัญหาด้วยการใช้อังกฤษบนจอ ไทยไว้ใน console
# =============================================================
import sys
import threading
import time
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import config          # noqa: E402
import camera          # noqa: E402
import detector as detector_mod  # noqa: E402
import hardware        # noqa: E402

GREEN = (80, 255, 80)
GREEN_DIM = (40, 130, 40)
AMBER = (0, 200, 255)
RED = (60, 60, 255)
FONT = cv2.FONT_HERSHEY_DUPLEX

# ค่าทั้งสี่ย้ายไป config.py แล้ว (25 ก.ค.) — main_click.py ใช้ชุดเดียวกัน
# เก็บสองแหล่งไว้เท่ากับรอให้มันเพี้ยนกัน เหมือนที่ simulator เพิ่งเพี้ยนจาก AIM_*_SIGN
# ระหว่างรันสลับทิศสดได้ด้วย z (pan) / x (tilt) — พอถูกทางกด p แล้วจดกลับไปแก้ config.py
STEP_FINE = config.KEY_STEP_FINE_DEG      # a/d/w/s
STEP_COARSE = config.KEY_STEP_COARSE_DEG  # A/D/W/S (กด shift)
KEY_PAN_SIGN = config.KEY_PAN_SIGN        # a → หันซ้าย, d → หันขวา
KEY_TILT_SIGN = config.KEY_TILT_SIGN      # w → เงยขึ้น, s → กดลง

# ปุ่มที่สั่ง pan(+) / tilt(-) จริง — เลื่อนตาม KEY_*_SIGN เอง ใช้ในบทเช็คทิศ HUD/HELP
PAN_POS_KEY = "a" if KEY_PAN_SIGN > 0 else "d"
TILT_NEG_KEY = "w" if KEY_TILT_SIGN < 0 else "s"

HELP = f"""
  a / d      pan ซ้าย/ขวา 1°      |  A / D   ทีละ 5°
  w / s      tilt ขึ้น/ลง 1°       |  W / S   ทีละ 5°
  z / x      สลับทิศ pan / tilt สดๆ — กดถ้ากดแล้วหันผิดข้าง (พอถูกทางกด p ไปแปะถาวร)
  c          กลับกลางลำ
  r          สั่ง config ขาใหม่ — ใช้ตอน "ตัวเลขเดินแต่ป้อมไม่ขยับ" (บอร์ดรีเซ็ตเพราะไฟตก)
  b          ทดสอบ slop: หมุน +5° แล้ว -5° กลับที่เดิม (ถ้าใกล้ลิมิตจะเข้าด้านในก่อน)
  i/j/k/l    เลื่อนจุด zero บน/ซ้าย/ลง/ขวา (คาลิเบรตสโคป — ทำท้ายสุด)
  f          ยิง 1 นัด (เร่งล้อ → บอกจังหวะหย่อนลูก → หยุดล้อ)
  g          หยุดล้อทันที (ฉุกเฉิน)
  y          เปิด/ปิด YOLO
  p          พิมพ์ค่าปัจจุบันลง console (ไว้ copy เข้า config.py)
  q / ESC    ออก

  🔎 วิธีเช็คทิศ (ทำข้อนี้ก่อนอย่างอื่น):
     กด {PAN_POS_KEY} (pan +) แล้วดูวัตถุนิ่งๆ ในภาพ
        ภาพเลื่อนไป "ซ้าย"  = AIM_SIGN = +1 ถูกแล้ว
        ภาพเลื่อนไป "ขวา"   = ต้องแก้ AIM_SIGN เป็น -1
     กด {TILT_NEG_KEY} (tilt -) แล้วดูวัตถุเดิม
        ภาพเลื่อน "ขึ้น"    = AIM_TILT_SIGN = +1 ถูกแล้ว
        ภาพเลื่อน "ลง"      = ต้องแก้ AIM_TILT_SIGN เป็น -1
"""


class ManualAim:
    def __init__(self):
        self.detect_on = "--no-detect" not in sys.argv
        print("กำลังเปิดกล้อง ...")
        self.cap = camera.open_camera()
        print("กำลังต่อ Arduino ...")
        self.turret = hardware.Turret()
        self.detector = detector_mod.get_detector() if self.detect_on else None
        print("พร้อม!", HELP)

        self.dets = []
        self.status = "MANUAL MODE  //  a-d-w-s = MOVE   Z/X = FLIP DIR   F = FIRE   Q = QUIT"
        self.status_color = GREEN
        # ทิศเริ่มจากค่าคงที่ด้านบน แต่ "สลับสด" ได้ด้วย z (pan) / x (tilt) โดยไม่ต้องปิดโปรแกรม
        # — ตัดวงจร "แก้ไฟล์→รันใหม่→เดา" ที่ทำให้ทิศวนไม่จบ พอหันถูกทางกด p เอาค่าไปแปะที่ KEY_*_SIGN
        self.pan_sign = KEY_PAN_SIGN
        self.tilt_sign = KEY_TILT_SIGN
        self.busy = False          # กำลังยิง/ทดสอบ slop อยู่ ห้ามสั่งซ้อน
        self._hw_fault = False     # บอร์ด throw ระหว่างยิง — ล็อกไม่ให้ยิงต่อจนกว่าจะ restart
        self._fire_cancel = threading.Event()  # g ต้องตัด feed window แม้ fire thread ยังอยู่
        self._fire_thread = None
        self._slop_thread = None   # เก็บไว้ join ตอนปิด — ไม่งั้นปิดบอร์ดทับ thread ที่ยังหมุนป้อมอยู่
        self._w, self._h = config.FRAME_WIDTH, config.FRAME_HEIGHT
        self._latest = None
        self._alive = True
        self._lock = threading.Lock()
        self._fps, self._frames, self._t0 = 0.0, 0, time.time()

    # ---------- worker: YOLO แยก thread ไม่ให้ภาพสะดุด ----------
    def _detect_loop(self):
        while self._alive:
            if not self.detect_on or self.detector is None:
                time.sleep(0.05)
                continue
            with self._lock:
                frame = self._latest
            if frame is None:
                time.sleep(0.01)
                continue
            try:
                self.dets = self.detector.detect_all(frame)
            except Exception as e:
                self._set(f"DETECT ERROR: {e}", RED)
                time.sleep(0.5)

    def _set(self, text, color=GREEN):
        # status ถูกส่งเข้า cv2.putText — em dash หรือข้อความ error ที่ไม่ใช่ ASCII จะกลายเป็นกล่องว่างบน HUD
        self.status = str(text).encode("ascii", "replace").decode("ascii")
        self.status_color = color

    def _zero_px(self):
        return (int(self._w / 2 + config.SCOPE_ZERO_OFFSET_PX[0]),
                int(self._h / 2 + config.SCOPE_ZERO_OFFSET_PX[1]))

    # ---------- ยิง: เร่งล้อ → บอกให้หย่อนลูก → หยุด ----------
    def _fire(self):
        if self._hw_fault:
            self._set("HARDWARE FAULT LATCHED  //  RESTART REQUIRED", RED)
            return

        self._fire_cancel.clear()
        self.busy = True

        def run():
            try:
                # ⚠ ต้องเช็ค cancel "ก่อน" spin_up ด้วย ไม่ใช่แค่หลัง — ระหว่าง
                # thread นี้ยังไม่ทันเริ่ม ถ้าคนกด f แล้วกด g ทันที ตัว g จะสั่ง
                # spin_down() ไปแล้ว แต่ thread เพิ่งมาถึงบรรทัดนี้พอดี แล้วเร่งล้อ
                # ใหม่ค้างอีก FLYWHEEL_SPINUP_S วินาที "หลังจาก" กดหยุดฉุกเฉินไปแล้ว
                if self._fire_cancel.is_set():
                    self._set("CANCELLED BEFORE SPIN-UP - WHEELS STAY STOPPED", AMBER)
                    return
                self._set(f"SPINNING UP {config.FLYWHEEL_SPINUP_S:.1f}s  //  DO NOT DROP YET",
                          AMBER)
                self.turret.spin_up()   # บล็อกจน FLYWHEEL_SPINUP_S ครบ (ล้อนิ่งแล้ว)
                if self._fire_cancel.is_set():
                    self._set("CANCELLED - WHEELS STOPPED", AMBER)
                    print("ยกเลิกช่วงป้อนลูกและหยุดล้อแล้ว")
                    return
                end = time.time() + config.FLYWHEEL_FEED_WINDOW_S
                while time.time() < end and not self._fire_cancel.is_set():
                    self._set(f">>>  DROP THE BALL NOW  <<<   {end - time.time():3.1f}s LEFT",
                              RED)
                    self._fire_cancel.wait(0.05)
                if self._fire_cancel.is_set():
                    self._set("CANCELLED - WHEELS STOPPED", AMBER)
                    print("ยกเลิกช่วงป้อนลูกและหยุดล้อแล้ว")
                else:
                    self._set("WINDOW CLOSED - WHEELS STOPPED  //  F FOR NEXT SHOT", GREEN)
            except Exception as e:
                self._hw_fault = True
                self._set(f"HARDWARE FAULT: {e}  //  RESTART REQUIRED", RED)
            finally:
                # ต้องหยุดล้อแม้ spin_up/feed จะ throw — ไม่เช่นนั้นล้อจะค้างเต็ม PWM ตอนมืออยู่ที่รางป้อน
                try:
                    self.turret.spin_down()
                except Exception as e:
                    self._hw_fault = True
                    self._set(f"HARDWARE FAULT: {e}  //  RESTART REQUIRED", RED)
                self.busy = False

        self._fire_thread = threading.Thread(target=run, daemon=True)
        self._fire_thread.start()

    # ---------- ทดสอบ slop: ไป-กลับแล้วดูว่าภาพกลับจุดเดิมไหม ----------
    def _slop_test(self):
        # ⚠ ตั้ง busy ที่นี่ ไม่ใช่ใน thread — ถ้าตั้งข้างใน จะมีช่องว่างระหว่าง
        # start() กับบรรทัดแรกของ worker ที่ busy ยังเป็น False คนกด b แล้ว f รัวๆ
        # จะผ่านด่าน busy เข้าไปสั่งยิงทับตอนป้อมกำลังหมุนทดสอบ
        self.busy = True
        start = self.turret.pan_angle

        def run():
            try:
                # ที่ pan 138° การไป +5° เดิมถูก clamp ที่ 140° จึงอ่าน phantom backlash — เข้าด้านในก่อนแทน
                direction = +1 if start + STEP_COARSE <= config.PAN_MAX else -1
                if start - STEP_COARSE < config.PAN_MIN and direction < 0:
                    raise RuntimeError("PAN RANGE TOO NARROW FOR A FULL SLOP EXCURSION")
                sign = "+" if direction > 0 else "-"
                self._set(f"SLOP TEST: REMEMBER A POINT IN FRAME - MOVING {sign}5deg ...", AMBER)
                time.sleep(1.2)
                self.turret.pan_by(direction * STEP_COARSE)
                time.sleep(1.2)
                self._set(f"SLOP TEST: MOVING BACK {('-' if direction > 0 else '+')}5deg ...", AMBER)
                self.turret.pan_by(-direction * STEP_COARSE)
                time.sleep(1.2)
                back = self.turret.pan_angle
                self._set(f"SLOP TEST DONE ({start:.0f} -> {back:.0f}deg) - "
                          f"BACK TO SAME POINT? IF NOT = SLOP", GREEN)
            except Exception as e:
                # เดิม RuntimeError "ช่วง pan แคบเกิน" ถูกโยนใน thread ที่ไม่มี except
                # → หายเงียบ ไม่มีอะไรขึ้นจอ คนกด b แล้วนึกว่าเครื่องไม่ตอบสนอง
                self._set(f"SLOP TEST ABORTED: {e}", AMBER)
            finally:
                # pan_to อาจ throw ได้ถ้าบอร์ดหลุด — ถ้าไม่กัน busy จะค้าง True ตลอดกาล
                # แล้วทุกปุ่มยกเว้น g จะใช้ไม่ได้อีกเลยจนกว่าจะปิดโปรแกรม
                try:
                    self.turret.pan_to(start)
                except Exception as e:
                    self._hw_fault = True
                    self._set(f"HARDWARE FAULT: {e}  //  RESTART REQUIRED", RED)
                self.busy = False

        self._slop_thread = threading.Thread(target=run, daemon=True)
        self._slop_thread.start()

    def _print_values(self):
        ox, oy = config.SCOPE_ZERO_OFFSET_PX
        print("\n" + "=" * 58)
        print(f"  pan  = {self.turret.pan_angle:.1f}°   tilt = {self.turret.tilt_angle:.1f}°")
        print(f"  SCOPE_ZERO_OFFSET_PX = [{ox}, {oy}]   # copy ไปวางใน src/config.py")
        print(f"  AIM_SIGN = {config.AIM_SIGN}   AIM_TILT_SIGN = {config.AIM_TILT_SIGN}"
              f"   AIM_KP = {config.AIM_KP}")
        print(f"  KEY_PAN_SIGN = {self.pan_sign:+d}   KEY_TILT_SIGN = {self.tilt_sign:+d}"
              f"   # ทิศปุ่มที่หันถูกแล้ว — แปะแทนค่าเดิมหัวไฟล์ tools/manual_aim.py")
        print("=" * 58 + "\n")
        self._set("VALUES PRINTED TO CONSOLE (switch to the black window to copy)", AMBER)

    # ---------- HUD ----------
    def render(self, frame):
        img = frame.copy()
        h, w = img.shape[:2]
        cx, cy = self._zero_px()

        # กรอบ detection (ตัวช่วยดูว่าโมเดลเห็นอะไร — ไม่มีผลกับการขยับ)
        for d in self.dets:
            x1, y1 = int(d.cx - d.w_px / 2), int(d.cy - d.h_px / 2)
            x2, y2 = int(d.cx + d.w_px / 2), int(d.cy + d.h_px / 2)
            cv2.rectangle(img, (x1, y1), (x2, y2), GREEN_DIM, 1)
            cv2.putText(img, f"{d.label} {d.conf:.2f}", (x1, max(14, y1 - 5)),
                        FONT, 0.5, GREEN_DIM, 1, cv2.LINE_AA)

        # จุด zero + เส้นกลางจอ (ไว้ดูว่าภาพเลื่อนไปทางไหนตอนหมุน)
        cv2.line(img, (cx - 60, cy), (cx - 12, cy), GREEN, 1)
        cv2.line(img, (cx + 12, cy), (cx + 60, cy), GREEN, 1)
        cv2.line(img, (cx, cy - 60), (cx, cy - 12), GREEN, 1)
        cv2.line(img, (cx, cy + 12), (cx, cy + 60), GREEN, 1)
        cv2.circle(img, (cx, cy), 3, GREEN, -1)
        cv2.circle(img, (cx, cy), 60, GREEN_DIM, 1)

        ox, oy = config.SCOPE_ZERO_OFFSET_PX
        cv2.putText(img, "COPPER DOME // MANUAL", (18, 30), FONT, 0.6, GREEN, 1, cv2.LINE_AA)
        right = (f"PAN {self.turret.pan_angle:5.1f}   TILT {self.turret.tilt_angle:5.1f}"
                 f"   ZERO {ox:+d},{oy:+d}   {self._fps:4.1f} FPS"
                 f"   YOLO {'ON' if self.detect_on else 'OFF'}")
        (tw, _), _ = cv2.getTextSize(right, FONT, 0.5, 1)
        cv2.putText(img, right, (w - tw - 18, 30), FONT, 0.5, GREEN, 1, cv2.LINE_AA)

        # แถวบน = จูนแมนนวลสดด้วย z/x ; แถวล่าง = ช่วยตั้ง AIM_SIGN ของออโต้ (คีย์เลื่อนตามทิศสด)
        pan_pos_key = "a" if self.pan_sign > 0 else "d"
        tilt_neg_key = "w" if self.tilt_sign < 0 else "s"
        cv2.putText(img, f"WRONG WAY?  [Z] flip a/d   [X] flip w/s      PAN {self.pan_sign:+d}   TILT {self.tilt_sign:+d}",
                    (18, h - 62), FONT, 0.5, AMBER, 1, cv2.LINE_AA)
        cv2.putText(img, f"AIM_SIGN calib: press {pan_pos_key} -> img shift LEFT,  press {tilt_neg_key} -> img shift UP",
                    (18, h - 44), FONT, 0.45, GREEN_DIM, 1, cv2.LINE_AA)
        cv2.line(img, (14, h - 34), (w - 14, h - 34), GREEN_DIM, 1)
        cv2.putText(img, self.status, (18, h - 12), FONT, 0.55,
                    self.status_color, 1, cv2.LINE_AA)
        return img

    # ---------- ลูปหลัก ----------
    def run(self):
        win = "COPPER DOME // MANUAL"
        cv2.namedWindow(win, cv2.WINDOW_NORMAL)
        threading.Thread(target=self._detect_loop, daemon=True).start()
        try:
            while True:
                ok, frame = self.cap.read()
                if not ok:
                    if cv2.waitKey(30) & 0xFF in (ord("q"), 27):
                        break
                    continue
                self._h, self._w = frame.shape[:2]
                with self._lock:
                    self._latest = frame

                cv2.imshow(win, self.render(frame))
                self._frames += 1
                if time.time() - self._t0 >= 0.5:
                    self._fps = self._frames / (time.time() - self._t0)
                    self._frames, self._t0 = 0, time.time()

                k = cv2.waitKey(1) & 0xFF
                if k == 255:
                    if cv2.getWindowProperty(win, cv2.WND_PROP_VISIBLE) < 1:
                        break     # ผู้ใช้กดกากบาทปิดหน้าต่าง
                    continue
                if not self._handle_key(k):
                    break
        finally:
            self._alive = False
            self._fire_cancel.set()
            # timeout ผูกกับค่า config ไม่ใช่เลขตายตัว — FLYWHEEL_SPINUP_S ยังเป็น
            # TODO ที่จะวัดจริงวันจูน ถ้าจูนขึ้นเกินเลขที่ hardcode ไว้ การปิดโปรแกรม
            # จะไปปิดบอร์ดทั้งที่ thread ยิงยังทำงานอยู่ (สั่งมอเตอร์ผ่านบอร์ดที่ปิดแล้ว)
            join_s = config.FLYWHEEL_SPINUP_S + config.FLYWHEEL_FEED_WINDOW_S + 1.0
            for th in (self._fire_thread, self._slop_thread):
                if th is not None:
                    th.join(timeout=join_s)
            try:
                self.turret.close()
            except Exception as e:
                print(f"ปิดบอร์ดไม่สำเร็จ: {e}")
            try:
                self.cap.release()
            except Exception as e:
                print(f"ปิดกล้องไม่สำเร็จ: {e}")
            cv2.destroyAllWindows()
            print("ปิดบอร์ด + กล้องเรียบร้อย")

    def _handle_key(self, k) -> bool:
        """คืน False = ออกจากโปรแกรม"""
        ch = chr(k) if 32 <= k < 127 else ""
        if k == 27 or ch in ("q", "Q"):
            return False

        # ระหว่างยิง/ทดสอบ slop ห้ามสั่งขยับซ้อน (จะเพี้ยนจนอ่านผลไม่ได้)
        if self.busy and ch not in ("g", "G"):
            self._set("BUSY - WAIT (G = EMERGENCY STOP WHEELS)", AMBER)
            return True

        # ทิศคุมจาก self.pan_sign / self.tilt_sign — สลับสดด้วย z / x (เริ่มจาก KEY_*_SIGN)
        if ch == "a":
            self.turret.pan_by(self.pan_sign * STEP_FINE)
        elif ch == "d":
            self.turret.pan_by(-self.pan_sign * STEP_FINE)
        elif ch == "A":
            self.turret.pan_by(self.pan_sign * STEP_COARSE)
        elif ch == "D":
            self.turret.pan_by(-self.pan_sign * STEP_COARSE)
        elif ch == "w":
            self.turret.tilt_by(self.tilt_sign * STEP_FINE)
        elif ch == "s":
            self.turret.tilt_by(-self.tilt_sign * STEP_FINE)
        elif ch == "W":
            self.turret.tilt_by(self.tilt_sign * STEP_COARSE)
        elif ch == "S":
            self.turret.tilt_by(-self.tilt_sign * STEP_COARSE)
        elif ch in ("z", "Z"):
            # สลับทิศ pan สดๆ — กดถ้า a/d หันผิดข้าง เห็นผลทันทีไม่ต้องรันใหม่
            self.pan_sign = -self.pan_sign
            self._set(f"PAN FLIPPED  //  now KEY_PAN_SIGN = {self.pan_sign:+d}  (test a/d again)", AMBER)
            print(f"สลับทิศ pan → KEY_PAN_SIGN = {self.pan_sign:+d}  (a/d กลับข้างแล้ว)")
        elif ch in ("x", "X"):
            # สลับทิศ tilt สดๆ — กดถ้า w/s หันผิดข้าง
            self.tilt_sign = -self.tilt_sign
            self._set(f"TILT FLIPPED  //  now KEY_TILT_SIGN = {self.tilt_sign:+d}  (test w/s again)", AMBER)
            print(f"สลับทิศ tilt → KEY_TILT_SIGN = {self.tilt_sign:+d}  (w/s กลับข้างแล้ว)")
        elif ch in ("c", "C"):
            self.turret.center()
            self._set("CENTERED", GREEN)
        elif ch in ("r", "R"):
            # กู้จากบอร์ดรีเซ็ตโดยไม่ต้องถอดสาย USB (ดู Turret.reinit_pins)
            try:
                self.turret.reinit_pins()
                self._hw_fault = False
                self._set("BOARD PINS RE-INITIALISED  //  TRY a/d NOW", AMBER)
            except Exception as e:
                self._set(f"RE-INIT FAILED: {e}", RED)
        elif ch in ("b", "B"):
            self._slop_test()
        elif ch in ("f", "F"):
            self._fire()
        elif ch in ("g", "G"):
            # ตั้ง cancel เสมอ ไม่ต้องเช็คว่า thread ยัง alive ไหม — จังหวะที่อันตราย
            # ที่สุดคือตอน thread เพิ่งถูก start แต่ยังไม่ทันเข้า spin_up (ดู _fire)
            # อ่านสถานะยิง "ก่อน" สั่ง cancel — ไว้เลือกข้อความ (เดิมอ้าง fire_active ที่ไม่มีตัวแปร → NameError)
            fire_active = self._fire_thread is not None and self._fire_thread.is_alive()
            self._fire_cancel.set()
            try:
                self.turret.spin_down()
            except Exception as e:
                self._hw_fault = True
                self._set(f"HARDWARE FAULT: {e}  //  RESTART REQUIRED", RED)
            else:
                if fire_active:
                    self._set("CANCELLED - WHEELS STOPPED", AMBER)
                else:
                    self._set("WHEELS STOPPED", GREEN)
        elif ch in ("y", "Y"):
            self.detect_on = not self.detect_on
            if not self.detect_on:
                self.dets = []
            elif self.detector is None:
                self.detector = detector_mod.get_detector()
            self._set(f"YOLO {'ON' if self.detect_on else 'OFF'}", GREEN)
        elif ch in ("p", "P"):
            self._print_values()
        elif ch == "i":
            config.SCOPE_ZERO_OFFSET_PX[1] -= 1
        elif ch == "k":
            config.SCOPE_ZERO_OFFSET_PX[1] += 1
        elif ch == "j":
            config.SCOPE_ZERO_OFFSET_PX[0] -= 1
        elif ch == "l":
            config.SCOPE_ZERO_OFFSET_PX[0] += 1
        return True


if __name__ == "__main__":
    ManualAim().run()
