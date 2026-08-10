# =============================================================
# main_click.py — จอมอนิเตอร์ยุทธวิธี (OpenCV ล้วน) สำหรับวันแข่ง
#   ธีมทหารเขียว + เส้น/จุดเล็งกลางจอ + ระบบล็อกเป้าแบบเครื่องบินรบ
#
# โหมดสโคป: กล้องติดลำกล้อง จุดเล็ง (zero) คือพิกเซลที่คาลิเบรตว่า "เป้าตรงนี้ = โดน"
# การเล็งมี 2 ทาง:
#   1) คลิก "ที่ตัวตุ๊กตา" (กรอบ detection) = ล็อกตุ๊กตาตัวนั้น → ป้อม pan+tilt
#      เอาเป้าเข้าจุด zero เอง (visual servoing 2 แกน) เป้าเล็งแดงเกาะตุ๊กตาไว้
#   2) สำรอง — ถ้าโมเดลมองไม่เห็น คลิก "ที่ว่างบนจอ" ตรงไหนก็ได้
#      ป้อมจะหันเอาพิกเซลนั้นมาที่จุด zero (ไม่พึ่ง detection)
#
# รันกับของจริง:  venv\Scripts\python.exe src\main_click.py
# รันโหมดจำลอง:   venv\Scripts\python.exe src\main_click.py --sim
# ดูจอบูตเฉยๆ:    venv\Scripts\python.exe src\main_click.py --boot-demo
#
# ตอนเปิด: bootstrap() เปิดอุปกรณ์ทีละขั้นโดยมีจอบูต (bootscreen.py) รายงานสด
# กล้อง+Arduino ถูกสั่งเปิดขนานไปกับการโหลดโมเดล → รวมเวลาเหลือ ~ขาที่ช้าที่สุด
#
# ปุ่ม:  คลิกซ้ายที่ตุ๊กตา = ล็อก+หันตาม | คลิกซ้ายที่ว่าง = เล็งจุดนั้น(สำรอง)
#        คลิกขวา = ยกเลิก/หยุดล็อก | I/J/K/L = เลื่อนจุด zero (ตอนคาลิเบรตสโคป)
#        W/A/S/D = ขยับป้อมเอง (ตัวใหญ่ = ก้าวหยาบ) | C = คืนป้อมกลางลำ
#        E = ปั่นล้อค้าง (ยิงรัวไม่ต้องเร่งใหม่ทุกนัด) | G = หยุดล้อฉุกเฉิน
#        F = ยิง | Q หรือ ESC = ออก
# =============================================================
import math
import sys
import threading
import time

import cv2

import aiming
import bootscreen
import config
import detector as detector_mod

# ---------- สีธีม (BGR) ----------
GREEN = (80, 255, 80)        # เขียว HUD หลัก
GREEN_DIM = (40, 130, 40)    # เขียวจาง — chrome/เส้นรอง
AMBER = (0, 200, 255)        # เหลืองอำพัน — เตือน/กำลังล็อก/โหมด TEST
RED = (60, 60, 255)          # แดง — เป้าที่ล็อก/ยิง
FONT = cv2.FONT_HERSHEY_DUPLEX


class _NullTurret:
    """ป้อมหลอกสำหรับโหมด --webcam: ดูภาพ/คลิกบนกล้องจริงได้โดยไม่ต้องต่อ
    Arduino — ทุกคำสั่งเป็น no-op (ไม่มีอะไรขยับ/ยิง)"""
    pan_angle = float(config.PAN_CENTER)
    tilt_angle = float(config.TILT_CENTER)

    def pan_to(self, angle): pass
    def pan_by(self, delta): pass
    def tilt_to(self, angle): pass
    def tilt_by(self, delta): pass
    def center(self): pass          # ปุ่ม c เรียกเมธอดนี้ — ไม่มี = AttributeError จอดับ
    def fire(self): pass
    def close(self): pass


class TacticalUI:
    def __init__(self, cap, turret, detector, mode, can_fire):
        # อุปกรณ์ทุกชิ้นถูกเปิดมาแล้วจากข้างนอก (ดู bootstrap()) — เดิม __init__
        # เป็นคนเปิดเอง ซึ่งแปลว่าระหว่างรอ 15-25 วิ ไม่มีทางเอาสถานะขึ้นจอได้เลย
        # เพราะยังไม่มีอะไรให้วาด
        self.cap = cap
        self.turret = turret
        self.detector = detector
        self.mode = mode
        self.can_fire = can_fire

        self.op = None               # None | "lock" (ป้อมกำลังหันตามตุ๊กตา) | "fire"
        self.locked_label = None     # ชนิดตุ๊กตาที่ล็อก (None = ล็อกแบบพิกเซล/ยังไม่ล็อก)
        self._anchor = None          # (cx, cy) ของ "ตัวที่คลิก" — ตัวชี้ขาดว่าล็อกตัวไหน
                                     # เมื่อชนิดเดียวกันโผล่หลายกรอบ (ไม่ต้องล้างตอน
                                     # ปลดล็อก: ใช้เมื่อ locked_label ไม่ None เท่านั้น
                                     # และ _start_lock เขียนทับให้ใหม่ทุกครั้ง)
        self.armed = False           # เล็งเสร็จ พร้อมยิง (โชว์เป้าเล็งแดง)
        self.mouse = (0, 0)
        self.dets = []               # detection ล่าสุด (worker เขียน, main อ่าน/วาด)
        self._latest = None
        self._last_shown = None
        self._w = config.FRAME_WIDTH
        self._h = config.FRAME_HEIGHT
        self._alive = False
        self._abort = False          # สั่ง aim_at เลิกกลางคัน (ปิดโปรแกรม/คลิกขวายกเลิก)
        self._op_thread = None
        self._shared_frame = None    # เฟรมที่ thread ล็อกส่งกลับมาระหว่างหันตาม
        self._shared_dets = []
        self._lock = threading.Lock()
        self.status = "CLICK A TOY TO LOCK  //  F TO FIRE"
        self.status_color = GREEN

        self._t0 = time.time()
        self._frames = 0
        self._fps = 0.0
        self._cam_fail = 0           # นับเฟรมที่อ่านกล้องไม่ได้ติดกัน (ดูลูปหลัก)
        self._hw_fault = False       # เจอ error ฝั่งฮาร์ดแวร์แล้ว — ห้ามยิงต่อจนกว่าจะรีสตาร์ท
        self.spin_hold = False       # ล้อ flywheel ถูกสั่งค้างไว้ด้วยปุ่ม E (ไม่ใช่ค้างจากนัดที่กำลังยิง)
        self._spin_thread = None     # spin_up() บล็อก FLYWHEEL_SPINUP_S — ห้ามรันบน thread จอ

        if list(config.SCOPE_ZERO_OFFSET_PX) == [0, 0]:
            # ไม่บล็อกการยิง — ต้องยิงถึงจะคาลิเบรตได้ แต่ต้องเห็นชัดว่ายังไม่ได้ตั้ง
            self.status = "!! SCOPE ZERO NOT CALIBRATED ([0,0]) - EXPECT SYSTEMATIC MISS !!"
            self.status_color = AMBER

    # ---------- เมาส์ ----------
    def on_mouse(self, event, x, y, flags, _):
        self.mouse = (x, y)
        if event == cv2.EVENT_RBUTTONDOWN:
            if self.op is not None:
                self._abort = True                 # ยกเลิกการล็อกที่กำลังหันตาม
            else:
                self.armed = False
                self.locked_label = None
                self._set_status("CLICK A TOY TO LOCK  //  F TO FIRE", GREEN)
            return
        if self.op is not None:
            return
        if event == cv2.EVENT_LBUTTONDOWN:
            toy = self._toy_under(x, y)
            if toy is not None:
                self._start_lock(toy)              # คลิกโดนตุ๊กตา → ล็อก+หันตาม
            else:
                self._aim_manual(x, y)             # คลิกที่ว่าง → เล็งพิกเซล (สำรอง)

    def _toy_under(self, x, y):
        """หา detection ที่จุดคลิกโดน (กรอบเล็กสุดถ้าซ้อน) ถ้าไม่โดนกรอบไหน
        เลือกตัวที่ศูนย์กลางใกล้จุดคลิกภายใน 90 px คืน None ถ้าไม่มีเลย"""
        inside = [d for d in self.dets
                  if abs(x - d.cx) <= d.w_px / 2 and abs(y - d.cy) <= d.h_px / 2]
        if inside:
            return min(inside, key=lambda d: d.w_px * d.h_px)
        near = [d for d in self.dets
                if ((x - d.cx) ** 2 + (y - d.cy) ** 2) ** 0.5 <= 90]
        return min(near, key=lambda d: (x - d.cx) ** 2 + (y - d.cy) ** 2) if near else None

    # ---------- ล็อกตุ๊กตา → ป้อมหันตาม (visual servoing) ----------
    def _start_lock(self, toy):
        """toy = Detection ที่คนคลิกโดน — ต้องส่ง "ตัวไหน" ไปด้วย ไม่ใช่แค่ "ชนิดอะไร"

        เดิมส่งแค่ toy.label แล้วลูปเล็งไปหาเองว่ากรอบชนิดนั้นที่ conf สูงสุดอยู่ไหน
        พอโมเดลอ่านช้างเป็น capybara ด้วย conf สูงกว่าตัวจริง ป้อมจึงหันไปหาช้าง
        ทั้งที่คนคลิกคาปิบาร่า (เจอจริง 29 ก.ค.) — พิกัดที่คลิกคือข้อมูลชิ้นเดียว
        ที่บอกได้ว่าคนหมายถึงตัวไหน ห้ามทิ้ง"""
        self._abort = False
        self.locked_label = toy.label
        self._anchor = (toy.cx, toy.cy)
        self.armed = False
        self.op = "lock"
        self._op_thread = threading.Thread(target=self._lock_sequence,
                                           args=(toy.label, self._anchor), daemon=True)
        self._op_thread.start()

    def _lock_sequence(self, label, anchor):
        try:
            self._set_status(f"ACQUIRING: {label.upper()} ...", AMBER)

            def on_frame(frame, det):
                with self._lock:
                    self._shared_frame = frame
                    self._shared_dets = [det] if det is not None else []

            # sweep=False: คนคลิกเลือกเป้าให้แล้ว ถ้าล็อกไม่ติดให้บอกเลย อย่าให้ป้อม
            # กวาดหนีไปจากตุ๊กตาที่คนเห็นอยู่กับตา (จอใช้ conf 0.20 แต่เส้นทางเล็ง
            # ใช้ 0.30 + ประตู — ตัวที่ conf 0.25 คลิกได้แต่ล็อกไม่ได้ เกิดขึ้นได้จริง)
            det = aiming.aim_at(self.turret, self.cap, self.detector, label,
                                on_frame, should_abort=lambda: self._abort,
                                sweep=False, anchor=anchor)
            if det is None:
                self.locked_label = None
                self._set_status("LOCK FAILED  //  CLICK ANYWHERE ON SCREEN TO AIM", AMBER)
                return
            self._anchor = (det.cx, det.cy)   # จบที่ตัวไหน จอต้องเกาะตัวนั้นต่อ
            self.armed = True
            self._announce_armed(label.upper())
        except Exception as e:
            self._set_status(f"ERROR: {e}", RED)
        finally:
            self.op = None

    # ---------- จุด zero ของสโคปบนจอ ----------
    def _zero_px(self):
        return (int(self._w / 2 + config.SCOPE_ZERO_OFFSET_PX[0]),
                int(self._h / 2 + config.SCOPE_ZERO_OFFSET_PX[1]))

    # ---------- เล็งพิกเซลเอง (สำรอง เมื่อโมเดลไม่เห็น) ----------
    def _aim_manual(self, x, y):
        if config.FOCAL_PX:
            zx, zy = self._zero_px()
            pan = math.degrees(math.atan2(x - zx, config.FOCAL_PX))
            tilt = math.degrees(math.atan2(y - zy, config.FOCAL_PX))
            want_pan = self.turret.pan_angle + config.AIM_SIGN * pan * config.CLICK_AIM_GAIN
            want_tilt = (self.turret.tilt_angle
                         - config.AIM_TILT_SIGN * tilt * config.CLICK_AIM_GAIN)
            self.turret.pan_by(config.AIM_SIGN * pan * config.CLICK_AIM_GAIN)
            self.turret.tilt_by(-config.AIM_TILT_SIGN * tilt * config.CLICK_AIM_GAIN)

            # ป้อมชนลิมิตแล้วหมุนได้ไม่ครบที่ขอ = ยังไม่ได้เล็งตรงจุดที่คลิก
            # ห้ามขึ้น "ON ZERO" (Codex เจอ 23 ก.ค.: ที่ pan 138° คลิกขวา 200px
            # ขอ +8.1° แต่ติดเพดาน 140° เหลือ error ~6° ทั้งที่จอบอกว่าล็อกแล้ว)
            short = max(abs(want_pan - self.turret.pan_angle),
                        abs(want_tilt - self.turret.tilt_angle))
            if short > 0.5:
                self.locked_label = None
                self.armed = False
                self._set_status(
                    f"AT TRAVEL LIMIT — {short:.1f}deg SHORT  //  MOVE THE TURRET BASE", AMBER)
                return
        self.locked_label = None
        self.armed = True
        self._announce_armed("MANUAL")

    def _announce_armed(self, what):
        self._set_status(f">> LOCKED: {what} // ON ZERO // F TO FIRE <<", RED)

    # ---------- ขยับป้อมเอง (W/A/S/D) ----------
    def _manual_move(self, dpan_steps, dtilt_steps, coarse):
        """ขยับป้อมทีละก้าว — ทิศ/ขนาดก้าวมาจาก config.KEY_* ชุดเดียวกับ manual_aim

        ห้ามขยับตอน op != None: ลูปเล็งอัตโนมัติกำลังคุมป้อมอยู่ ถ้าแทรกเข้าไป
        ป้อมจะสู้กันเอง แล้ว error ที่ลูปกำลังไล่ปิดจะเพี้ยนโดยหาสาเหตุไม่เจอ
        (ปุ่ม c ก็กันด้วยเงื่อนไขเดียวกัน) — คลิกขวายกเลิกก่อนถึงจะขยับเองได้"""
        if self.op is not None:
            self._set_status("BUSY  //  RIGHT-CLICK TO CANCEL FIRST", AMBER)
            return
        if self._hw_fault:
            self._set_status("HARDWARE FAULT LATCHED  //  RESTART REQUIRED", RED)
            return
        step = config.KEY_STEP_COARSE_DEG if coarse else config.KEY_STEP_FINE_DEG
        try:
            if dpan_steps:
                self.turret.pan_by(config.KEY_PAN_SIGN * dpan_steps * step)
            if dtilt_steps:
                self.turret.tilt_by(config.KEY_TILT_SIGN * dtilt_steps * step)
        except Exception as e:
            self._hw_fault = True
            self._set_status(f"HARDWARE FAULT: {e}  //  RESTART REQUIRED", RED)
            return
        # ขยับเองแล้ว = จุดที่เคยล็อกไว้ไม่ตรงอีกต่อไป ต้องล้างสถานะพร้อมยิงทิ้ง
        # ไม่งั้นจอยังขึ้น LOCKED ทั้งที่ลำกล้องหันไปทางอื่นแล้ว = ยิงพลาดโดยเชื่อจอ
        self.armed = False
        self.locked_label = None
        self._set_status(
            f"MANUAL  PAN {self.turret.pan_angle:.1f}  TILT {self.turret.tilt_angle:.1f}"
            f"  //  CLICK A TOY TO LOCK", GREEN)

    # ---------- ปั่นล้อค้าง (E) / หยุดฉุกเฉิน (G) ----------
    def toggle_spin_hold(self):
        """สั่งล้อ flywheel ค้างความเร็วไว้ ไม่ต้องเร่งใหม่ทุกนัด

        hardware.spin_up() ออกแบบมาให้ UI สั่งค้างเองได้อยู่แล้ว (ดู docstring ที่นั่น)
        แต่มันบล็อก FLYWHEEL_SPINUP_S — เรียกบน thread จอตรงๆ = จอค้าง 1.5 วิ
        จึงโยนลง thread แล้วให้จอเดินต่อระหว่างเร่ง"""
        if not self.can_fire:
            self._set_status("TEST MODE  //  NO TURRET", AMBER)
            return
        if self._hw_fault:
            self._set_status("HARDWARE FAULT LATCHED  //  RESTART REQUIRED", RED)
            return
        if config.LAUNCHER != "flywheel":
            self._set_status(f"LAUNCHER IS {config.LAUNCHER.upper()}  //  NO WHEELS", AMBER)
            return
        if getattr(self.turret, "spin_up", None) is None:
            self._set_status("NO FLYWHEEL ON THIS TURRET", AMBER)
            return
        if self.spin_hold:
            self.stop_wheels(reason="WHEELS STOPPED")
            return
        if self._spin_thread is not None and self._spin_thread.is_alive():
            return                     # กำลังเร่งอยู่ กด E รัวไม่ต้องซ้อน
        if self.op is not None:
            self._set_status("BUSY  //  WAIT FOR CURRENT SHOT", AMBER)
            return

        self.spin_hold = True          # ตั้งก่อนเร่ง เพื่อให้ G ที่กดระหว่างเร่งยกเลิกได้
        self._set_status(
            f"SPINNING UP {config.FLYWHEEL_SPINUP_S:.1f}s  //  KEEP HANDS CLEAR", RED)

        def _spin():
            try:
                self.turret.spin_up()
            except Exception as e:
                self.spin_hold = False
                self._hw_fault = True
                self._set_status(f"HARDWARE FAULT: {e}  //  RESTART REQUIRED", RED)
                return
            if self.spin_hold:         # ยังไม่ถูกสั่งหยุดระหว่างเร่ง
                self._set_status("WHEELS HOLDING  //  F TO FIRE  //  E OR G TO STOP", RED)
            else:
                # กด G ระหว่างเร่ง — spin_down() ตอนนั้นสั่งไปก่อนที่ spin_up จะจบ
                # ต้องสั่งซ้ำ ไม่งั้นล้อค้างหมุนต่อ (เคสเดียวกับที่ manual_aim เตือนไว้)
                self.stop_wheels(reason="CANCELLED  //  WHEELS STOPPED")

        self._spin_thread = threading.Thread(target=_spin, daemon=True)
        self._spin_thread.start()

    def stop_wheels(self, reason="WHEELS STOPPED"):
        """หยุดล้อทันที — ปุ่ม G ใช้ได้ตลอดเวลา แม้กำลังยิง/กำลังเร่ง"""
        self.spin_hold = False
        spin_down = getattr(self.turret, "spin_down", None)
        if spin_down is None:
            return
        try:
            spin_down()
        except Exception as e:
            self._hw_fault = True
            self._set_status(f"HARDWARE FAULT: {e}  //  RESTART REQUIRED", RED)
        else:
            self._set_status(reason, GREEN)

    # ---------- ยิง ----------
    def start_fire(self):
        if self.op is not None:
            return
        if not self.can_fire:
            self._set_status("TEST MODE  //  NO TURRET - LOCK & AIM ONLY", AMBER)
            return
        if self._hw_fault:
            self._set_status("HARDWARE FAULT LATCHED  //  RESTART BEFORE FIRING", RED)
            return
        if not self.armed:
            self._set_status("LOCK A TARGET FIRST", RED)
            return
        self.op = "fire"
        self._abort = False
        self._op_thread = threading.Thread(target=self._fire_sequence, daemon=True)
        self._op_thread.start()

    def _fire_sequence(self):
        try:
            # flywheel แยกเป็น 2 จังหวะเพื่อ "บอกคนป้อนลูก" ว่าล้อนิ่งเมื่อไหร่ —
            # turret.fire() รวบทุกอย่างไว้ในคำสั่งเดียว จอจะค้างที่ FIRING ตลอด
            # คนหย่อนไม่รู้จังหวะ หย่อนก่อนล้อนิ่ง = นัดนั้นเบากว่าเพื่อน จุดตกเพี้ยนจาก zero
            # (โหมดสโคปตั้งอยู่บนสมมติฐานว่าทุกนัดแรงเท่ากัน — ดู hardware._fire_flywheel)
            spin_up = getattr(self.turret, "spin_up", None)  # SimTurret ไม่มี → ตกไปทาง fire()
            if config.LAUNCHER == "flywheel" and spin_up is not None:
                # ล้อค้างอยู่แล้วจากปุ่ม E = ข้ามขาเร่ง เปิดหน้าต่างหย่อนลูกเลย
                # (นี่คือเหตุผลที่ hardware แยก spin_up/spin_down ออกมาให้ UI สั่งเอง)
                if not self.spin_hold:
                    self._set_status(
                        f"SPINNING UP {config.FLYWHEEL_SPINUP_S:.1f}s  //  DO NOT DROP YET", AMBER)
                    spin_up()
                end = time.time() + config.FLYWHEEL_FEED_WINDOW_S
                while time.time() < end and not self._abort:
                    self._set_status(
                        f">>>  DROP THE BALL NOW  <<<   {end - time.time():3.1f}s LEFT", RED)
                    time.sleep(0.05)
                if self._abort:
                    self._set_status("CANCELLED  //  WHEELS STOPPED", GREEN)
                elif self.spin_hold:
                    self._set_status("WHEELS STILL HOLDING  //  F FOR NEXT SHOT", RED)
                else:
                    self._set_status("WHEELS STOPPED  //  F FOR NEXT SHOT", GREEN)
            else:
                self._set_status("FIRING", RED)
                self.turret.fire()
                self._set_status("SHOT AWAY", GREEN)
        except Exception as e:
            # ฮาร์ดแวร์มีปัญหากลางลำ — ห้ามให้จอกลับไปสภาพ "พร้อมยิง" เฉยๆ
            # (ล้ออาจยังหมุนอยู่ และนัดต่อไปจะเจอปัญหาเดิม) ล็อกไม่ให้ยิงจนกว่าจะรีสตาร์ท
            self._hw_fault = True
            self.armed = False
            self._set_status(f"HARDWARE FAULT: {e}  //  RESTART REQUIRED", RED)
        finally:
            # ⚠ หยุดล้อใน finally เสมอ — ถ้า throw ระหว่าง spin_up/หน้าต่างหย่อนลูก
            # โค้ดเดิมข้าม spin_down() ไปเลย = ล้อหมุนเต็มสปีดค้างไว้ โดยมีมือคน
            # อยู่ตรงช่องหย่อนลูกพอดี (บั๊กที่เขียนเองเมื่อเช้า 23 ก.ค.)
            #
            # ยกเว้นเดียว: คนสั่งค้างล้อไว้เองด้วยปุ่ม E และนัดนี้จบดี — ตั้งใจให้หมุนต่อ
            # ถ้ามี error หรือถูกยกเลิก ยังหยุดเหมือนเดิม (ล้างธง hold ทิ้งด้วย)
            # เพราะตอนนั้นเราไม่รู้แล้วว่าล้ออยู่ในสภาพไหน
            keep_spinning = self.spin_hold and not self._hw_fault and not self._abort
            if not keep_spinning:
                self.spin_hold = False
                try:
                    spin_down = getattr(self.turret, "spin_down", None)
                    if spin_down is not None:
                        spin_down()
                except Exception:
                    pass  # พยายามหยุดแบบ best-effort — error จริงรายงานไปแล้วข้างบน
            self.op = None

    # ---------- เลื่อนจุด zero (ตอนคาลิเบรตสโคป — ยิงจริงแล้วขยับจุดให้ทับรอยโดน) ----------
    def _nudge_zero(self, dx, dy):
        config.SCOPE_ZERO_OFFSET_PX[0] += dx
        config.SCOPE_ZERO_OFFSET_PX[1] += dy
        ox, oy = config.SCOPE_ZERO_OFFSET_PX
        # ค่าอยู่แค่ในหน่วยความจำ — จดลง config.py ถึงจะติดถาวร (โชว์ทั้งจอและ console)
        print(f"SCOPE_ZERO_OFFSET_PX = [{ox}, {oy}]   # copy ไปวางใน config.py")
        self._set_status(f"ZERO OFFSET ({ox:+d}, {oy:+d})  //  WRITE IT INTO config.py !", AMBER)

    def _set_status(self, text, color=GREEN):
        # status ถูกวาดด้วย cv2.putText ซึ่งใช้ฟอนต์ Hershey = ASCII ล้วน
        # อักขระอื่น (ไทย, em dash, ·) ออกมาเป็นกล่องว่างบนจอ. ตาข่ายกันพลาดตรงนี้
        # ครอบ error message ที่มาจากข้างนอกด้วย (เช่น exception ภาษาไทยจาก camera.py)
        # — ข้อความที่เราเขียนเองต้องเป็น ASCII อยู่แล้วตั้งแต่ต้นทาง
        self.status = str(text).encode("ascii", "replace").decode("ascii")
        self.status_color = color

    # ---------- วาด HUD ----------
    def _draw_reticle(self, img):
        """เส้น/จุดเล็งที่จุด zero ของสโคป (เขียว) — "เป้าอยู่ตรงนี้ = โดน" """
        cx, cy = self._zero_px()
        gap, arm = 16, 46
        cv2.line(img, (cx - arm, cy), (cx - gap, cy), GREEN, 1)
        cv2.line(img, (cx + gap, cy), (cx + arm, cy), GREEN, 1)
        cv2.line(img, (cx, cy - arm), (cx, cy - gap), GREEN, 1)
        cv2.line(img, (cx, cy + gap), (cx, cy + arm), GREEN, 1)
        cv2.circle(img, (cx, cy), 3, GREEN, -1)
        cv2.circle(img, (cx, cy), 60, GREEN_DIM, 1)

    def _draw_lock(self, img, cx, cy, hw, hh, blink, text="LOCK"):
        """เป้าเล็งแดงแบบล็อกมิสไซล์ (ไม่มีเส้นตัดจากมุมจอแล้ว — รกตา)
        ครอบกรอบตุ๊กตาที่ล็อก หรือครอบกลางจอ (โหมดพิกเซล)

        text = ชนิด+conf ของตัวที่ล็อกจริง ไม่ใช่คำว่า LOCK เฉยๆ — คนยิงต้องเห็น
        กับตาว่าระบบคิดว่ากำลังล็อกอะไรอยู่ ก่อนกด F (29 ก.ค.)"""
        phase = time.time() * 7
        pulse = int(6 + 9 * abs(math.sin(phase)))
        cv2.rectangle(img, (cx - hw, cy - hh), (cx + hw, cy + hh), RED, 2)
        cv2.rectangle(img, (cx - hw - pulse, cy - hh - pulse),
                      (cx + hw + pulse, cy + hh + pulse), RED, 1)
        cv2.drawMarker(img, (cx, cy), RED, cv2.MARKER_DIAMOND, 18, 2)
        cv2.drawMarker(img, (cx, cy), RED, cv2.MARKER_CROSS, 36, 1)
        if blink:
            txt = f"v {text} v"
            (tw, _), _ = cv2.getTextSize(txt, FONT, 0.6, 2)
            cv2.putText(img, txt, (cx - tw // 2, cy - hh - 14),
                        FONT, 0.6, RED, 2, cv2.LINE_AA)

    def _draw_hint(self, img, d, disputed=False):
        """กรอบ detection = "ตัวช่วยเล็ง" สีเขียว (โมเดลเห็นอะไร ไม่ใช่ตัวตัดสิน)

        disputed = ชนิดนี้โผล่เกิน 1 กรอบ ซึ่งเป็นไปไม่ได้ในสนามจริง (ชนิดละตัว)
        ⇒ ระบายเหลืองพร้อม "?" ให้คนรู้ว่าอย่างน้อยหนึ่งกรอบนี้ผิดแน่ ต้องเลือกเอง
        ว่าตัวไหนของจริง (คลิกตัวไหน ป้อมไปตัวนั้น — ดู _start_lock)"""
        color = AMBER if disputed else GREEN
        x1, y1 = int(d.cx - d.w_px / 2), int(d.cy - d.h_px / 2)
        x2, y2 = int(d.cx + d.w_px / 2), int(d.cy + d.h_px / 2)
        L = max(16, int(min(d.w_px, d.h_px) * 0.32))
        for (px, py, sx, sy) in ((x1, y1, 1, 1), (x2, y1, -1, 1),
                                  (x1, y2, 1, -1), (x2, y2, -1, -1)):
            px += sx * 4
            py += sy * 4
            cv2.line(img, (px, py), (px + sx * L, py), color, 2)
            cv2.line(img, (px, py), (px, py + sy * L), color, 2)
        # ป้ายชื่อ+conf บนแถบเข้ม ให้อ่านชัดบนพื้นหลังอะไรก็ได้
        label = f"{'? ' if disputed else ''}{d.label.upper()} {int(d.conf * 100):02d}%"
        (tw, th), _ = cv2.getTextSize(label, FONT, 0.55, 1)
        ly = max(th + 8, y1 - 6)
        cv2.rectangle(img, (x1, ly - th - 6), (x1 + tw + 8, ly + 2), (15, 35, 15), -1)
        cv2.putText(img, label, (x1 + 4, ly - 2), FONT, 0.55, color, 1, cv2.LINE_AA)

    def _draw_chrome(self, img, blink):
        h, w = img.shape[:2]
        m, L = 14, 34
        for (px, py, sx, sy) in ((m, m, 1, 1), (w - m, m, -1, 1),
                                  (m, h - m, 1, -1), (w - m, h - m, -1, -1)):
            cv2.line(img, (px, py), (px + sx * L, py), GREEN, 2)
            cv2.line(img, (px, py), (px, py + sy * L), GREEN, 2)

        cv2.putText(img, "COPPER DOME // SCOPE", (m + 8, 32),
                    FONT, 0.6, GREEN, 1, cv2.LINE_AA)
        rec = "* " if blink else "  "
        right = (f"{rec}{self.mode}   PAN {self.turret.pan_angle:5.1f}"
                 f"   TILT {self.turret.tilt_angle:5.1f}   {self._fps:4.1f} FPS")
        (tw, _), _ = cv2.getTextSize(right, FONT, 0.55, 1)
        cv2.putText(img, right, (w - m - tw - 8, 32), FONT, 0.55, GREEN, 1, cv2.LINE_AA)

        # ล้อหมุนค้างอยู่ = อันตรายกับมือที่รางป้อนลูก ต้องเห็นตลอดเวลา ไม่ใช่แค่
        # ตอน status บรรทัดล่างบังเอิญพูดถึง (status ถูกทับด้วยข้อความอื่นได้ตลอด)
        if self.spin_hold:
            warn = "!! WHEELS SPINNING !!" if blink else "   WHEELS SPINNING   "
            (ww, _), _ = cv2.getTextSize(warn, FONT, 0.7, 2)
            cv2.putText(img, warn, ((w - ww) // 2, 68), FONT, 0.7, RED, 2, cv2.LINE_AA)

        cv2.line(img, (m, h - 46), (w - m, h - 46), GREEN_DIM, 1)
        cv2.putText(img, self.status, (m + 8, h - 20),
                    FONT, 0.6, self.status_color, 1, cv2.LINE_AA)

    def _tint(self, img):
        """โทนจอมอนิเตอร์อมเขียว — cv2.convertScaleAbs (เร็ว ~6ms/เฟรม)"""
        img[:, :, 0] = cv2.convertScaleAbs(img[:, :, 0], alpha=0.75)   # B ลง 25%
        img[:, :, 2] = cv2.convertScaleAbs(img[:, :, 2], alpha=0.88)   # R ลง 12%

    def _locked_det(self, dets):
        """กรอบของ "ตัวที่ล็อกไว้" ในเฟรมนี้ — ชนิดเดียวกันและใกล้ anchor ที่สุด

        เดิมวนทั้งลิสต์แล้วให้ตัวสุดท้ายที่ชื่อตรงชนะ: ถ้าโมเดลรายงานชื่อเดียวกัน
        สองกรอบ (ช้างถูกอ่านเป็น capybara ด้วย) เป้าแดงจะกระโดดสลับไปมาระหว่าง
        สองตัวทุกเฟรม ตอนนี้ detect_all ตัดให้เหลือชนิดละกรอบแล้ว ตรงนี้จึงเป็น
        ตาข่ายชั้นสุดท้าย (และยังต้องมี เผื่อปิด config.UNIQUE_TARGETS ตอนซ้อม)"""
        if not self.locked_label:
            return None
        same = [d for d in dets if d.label == self.locked_label]
        if not same:
            return None
        if self._anchor is None:
            best = max(same, key=lambda d: d.conf)
        else:
            ax, ay = self._anchor
            best = min(same, key=lambda d: (d.cx - ax) ** 2 + (d.cy - ay) ** 2)
        if self.op is None:
            # ระหว่าง op == "lock" ลูปเล็งถือ anchor ชุดของมันเองอยู่ ห้ามแทรก
            self._anchor = (best.cx, best.cy)
        return best

    def render(self, frame, dets):
        img = frame.copy()
        self._tint(img)
        blink = int(time.time() * 2) % 2 == 0

        locked_det = self._locked_det(dets)
        disputed = detector_mod.duplicate_labels(dets)
        for d in dets:
            if d is not locked_det:
                self._draw_hint(img, d, d.label in disputed)

        manual = self.armed and self.locked_label is None
        if not manual:
            self._draw_reticle(img)       # โชว์ศูนย์กลางไว้เป็นตัวอ้างอิง

        if locked_det is not None:        # ล็อกตุ๊กตา: เป้าแดงเกาะตุ๊กตา
            self._draw_lock(img, int(locked_det.cx), int(locked_det.cy),
                            int(locked_det.w_px / 2) + 6, int(locked_det.h_px / 2) + 6,
                            blink,
                            f"{locked_det.label.upper()} {int(locked_det.conf * 100)}%")
        elif manual:                      # ล็อกพิกเซล: เป้าแดงที่จุด zero
            zx, zy = self._zero_px()
            self._draw_lock(img, zx, zy, 34, 34, blink, "MANUAL")

        self._draw_chrome(img, blink)
        return img

    # ---------- thread ตรวจจับ (แยกจากการแสดงผล) ----------
    def _detect_worker(self):
        """รัน detect_all บนเฟรมล่าสุด เก็บผลไว้ที่ self.dets เป็น "ตัวช่วยเล็ง"
        ตรวจเฉพาะเฟรมใหม่ (identity) กันวน detect เฟรมเดิมกิน CPU
        พักตอน op=="lock" เพราะ thread ล็อกเป็นเจ้าของกล้องตอนนั้น"""
        last = None
        fails = 0
        while self._alive:
            if self.op == "lock":
                time.sleep(0.02)
                continue
            with self._lock:
                frame = self._latest
            if frame is None or frame is last:
                time.sleep(0.005)
                continue
            last = frame
            try:
                self.dets = self.detector.detect_all(frame)
                fails = 0
            except Exception as e:
                # เดิม `pass` เฉยๆ — กรอบเก่าค้างทับเฟรมใหม่ คนคลิกกรอบผีที่ไม่มีอยู่จริง
                # แล้วไปรอ lock timeout โดยไม่มีใครรู้ว่าโมเดลตายไปแล้ว
                self.dets = []
                fails += 1
                if fails == 1 or fails % 20 == 0:
                    self._set_status(f"DETECTOR ERROR: {e}", RED)
                time.sleep(0.2)   # ถอยหน่อย อย่ากระหน่ำเรียกซ้ำตอนพัง

    # ---------- ลูปหลัก ----------
    def run(self):
        win = WINDOW                               # หน้าต่างเดียวกับจอบูต — ภาพกล้อง
        cv2.namedWindow(win, cv2.WINDOW_AUTOSIZE)  # ขึ้นแทนที่เลย ไม่มีหน้าต่างเด้งซ้อน
                                                   # AUTOSIZE = 1:1 พิกัดคลิกตรงเฟรม
        cv2.setMouseCallback(win, self.on_mouse)
        self._alive = True
        worker = threading.Thread(target=self._detect_worker, daemon=True)
        worker.start()
        try:
            last_rendered = None      # identity ของเฟรมที่ render ไปแล้ว — กัน main loop
                                      # วน render เฟรมเดิมซ้ำๆ ตอน lock (แย่ง GIL/lock กับ
                                      # thread ล็อก = ต้นเหตุกระตุกจริง Codex ชี้ 22 ก.ค.)
            while True:
                if self.op == "lock":
                    # thread ล็อกเป็นเจ้าของกล้องตอนหันตาม — main ห้ามอ่านกล้อง
                    # (VideoCapture ไม่ thread-safe) โชว์เฟรมที่มันส่งมาผ่าน on_frame
                    with self._lock:
                        shared = self._shared_frame
                        dets = list(self._shared_dets)
                    frame = shared if shared is not None else self._last_shown
                    fresh = frame is not None and frame is not last_rendered
                else:
                    # ปกติ + ตอนยิง (fire ไม่แตะกล้อง) — main อ่านกล้องที่นี่ที่เดียว
                    ok, frame = self.cap.read()
                    if not ok:
                        # ⚠ ห้าม `continue` เปล่าๆ ตรงนี้ (บั๊กเดิม 23 ก.ค.) — เส้นทางนี้
                        # ไม่ผ่าน cv2.waitKey เลย พอกล้องหลุด (จอมือถือล็อก / Camo ไม่อยู่
                        # หน้าสุด = เคสที่เอกสารเราเขียนเองว่าเกิดบ่อย) จะกลายเป็นลูปตัน
                        # ที่ไม่ pump event ของหน้าต่าง → Q/ESC/กากบาท/เมาส์ ตายหมด
                        # ต้องปิดด้วย Task Manager กลางสนามแข่ง
                        self._cam_fail += 1
                        if self._cam_fail == 1 or self._cam_fail % 20 == 0:
                            self._set_status(
                                "CAMERA LOST  //  WAKE PHONE + BRING CAMO TO FRONT", RED)
                        k = cv2.waitKey(30) & 0xFF
                        if k in (ord('q'), 27) or \
                                cv2.getWindowProperty(win, cv2.WND_PROP_VISIBLE) < 1:
                            break
                        continue
                    if self._cam_fail:
                        self._cam_fail = 0
                        self._set_status("CAMERA BACK  //  CLICK A TOY TO LOCK", GREEN)
                    self._h, self._w = frame.shape[:2]
                    self._last_shown = frame
                    with self._lock:
                        self._latest = frame
                    dets = self.dets
                    fresh = True

                if frame is None:
                    cv2.waitKey(1)
                    continue
                # render เฉพาะตอนมี "เฟรมใหม่จริง" — ถ้าเฟรมเดิม (thread ล็อกยังไม่ส่งอันใหม่)
                # แค่รอสั้นๆ ไม่ต้อง render/imshow ซ้ำ เปลือง CPU + แย่ง GIL กับ thread ล็อก
                if fresh:
                    cv2.imshow(win, self.render(frame, dets))
                    last_rendered = frame
                    self._frames += 1
                    if time.time() - self._t0 >= 0.5:
                        self._fps = self._frames / (time.time() - self._t0)
                        self._frames, self._t0 = 0, time.time()

                k = cv2.waitKey(1 if fresh else 15) & 0xFF
                if k in (ord('q'), 27):
                    break
                elif k == ord('f'):
                    self.start_fire()
                elif k == ord('i'):
                    self._nudge_zero(0, -5)
                elif k == ord('k'):
                    self._nudge_zero(0, +5)
                elif k == ord('j'):
                    self._nudge_zero(-5, 0)
                elif k == ord('l'):
                    self._nudge_zero(+5, 0)
                elif k == ord('c') and self.op is None:
                    self.turret.center()
                    self.armed = False
                    self.locked_label = None
                    self._set_status("TURRET CENTERED", GREEN)
                # ---- ขยับป้อมเอง: ตัวเล็ก = ก้าวละเอียด, ตัวใหญ่ (shift) = ก้าวหยาบ ----
                elif k in (ord('a'), ord('A')):
                    self._manual_move(+1, 0, coarse=k == ord('A'))
                elif k in (ord('d'), ord('D')):
                    self._manual_move(-1, 0, coarse=k == ord('D'))
                elif k in (ord('w'), ord('W')):
                    self._manual_move(0, +1, coarse=k == ord('W'))
                elif k in (ord('s'), ord('S')):
                    self._manual_move(0, -1, coarse=k == ord('S'))
                # ---- ล้อ flywheel ----
                elif k in (ord('e'), ord('E')):
                    self.toggle_spin_hold()
                elif k in (ord('g'), ord('G')):
                    # หยุดฉุกเฉิน — ต้องกดได้ทุกสถานะ รวมถึงตอนกำลังยิง/กำลังเร่ง
                    # _abort ทำให้หน้าต่างหย่อนลูกที่ค้างอยู่เลิกทันทีด้วย
                    self._abort = True
                    self.stop_wheels(reason="EMERGENCY STOP  //  WHEELS STOPPED")
                if cv2.getWindowProperty(win, cv2.WND_PROP_VISIBLE) < 1:
                    break
        finally:
            self._abort = True
            self._alive = False
            if self._op_thread is not None:
                self._op_thread.join(timeout=4.0)
            worker.join(timeout=1.0)
            # แยก try ของแต่ละอย่าง — เดิมถ้า turret.close() throw (Arduino หลุด)
            # จะข้าม cap.release() ไปเลย ปล่อยให้ Camo ค้างจนกว่า process จะตายจริง
            try:
                self.turret.close()
            except Exception as e:
                print(f"[shutdown] ปิดบอร์ดไม่สำเร็จ: {e}")
            try:
                self.cap.release()
            except Exception as e:
                print(f"[shutdown] ปิดกล้องไม่สำเร็จ: {e}")
            cv2.destroyAllWindows()


WINDOW = "Copper Dome // Tactical"


def _prefetch(fn):
    """เริ่มงานช้าไว้ล่วงหน้าบน thread แยก แล้วค่อยไปเก็บผลทีหลังด้วย _collect()

    ทำไมคุ้ม: เปิดกล้อง Camo (~2-4s ส่วนใหญ่นั่งรอ stream ตื่น) กับจับมือ Arduino
    (~2.5s ที่เป็น time.sleep ตรงๆ ใน hardware.Turret) ไม่ได้ใช้ CPU เลย ทับเวลา
    กับ import torch + โหลดโมเดลได้สบาย ⇒ เวลาเปิดโปรแกรมเหลือประมาณ "ขาที่ช้าที่สุด"
    แทนที่จะเป็นผลรวมของทุกขา

    ปลอดภัยไหม: VideoCapture ถูกเปิด/อ่านข้าม thread อยู่แล้วในโปรแกรมนี้
    (thread ล็อกเรียก cap.read() ระหว่าง aim_at) ส่วน pyfirmata2 ก็รัน reader
    thread ของตัวเองอยู่แล้ว — ไม่ได้เพิ่มสมมติฐานใหม่
    """
    box = {}

    def run():
        try:
            box["value"] = fn()
        except BaseException as e:   # noqa: BLE001 — ส่งต่อให้ขั้นที่ไป collect โยนแทน
            box["error"] = e

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread, box


def _collect(pre):
    """รอ prefetch ให้จบแล้วคืนผล — ถ้าข้างในพัง โยน exception เดิมออกมาตรงนี้
    (จอบูตจะได้ขึ้น FAIL ที่ "ขั้นตอนที่เกี่ยวข้องจริง" ไม่ใช่ที่ขั้นแรกสุด)"""
    thread, box = pre
    thread.join()
    if "error" in box:
        raise box["error"]
    return box["value"]


def _safety_check(note):
    """ตรวจสภาพก่อนปล่อยให้ยิง — ไม่บล็อก แต่ต้องเห็นชัดว่าอะไรยังไม่พร้อม"""
    if config.LAUNCHER not in ("flywheel", "crossbow"):
        raise ValueError(f"config.LAUNCHER = {config.LAUNCHER!r} ไม่ถูกต้อง")
    if list(config.SCOPE_ZERO_OFFSET_PX) == [0, 0]:
        # ยังยิงได้ (ต้องยิงถึงจะคาลิเบรตได้) แต่ห้ามเงียบ — นี่คือตัวที่ทำให้
        # พลาดเป็นระบบทุกนัด ดู issue #16
        note.warn("SCOPE ZERO NOT CALIBRATED - expect systematic miss")
    else:
        note(f"scope zero {tuple(config.SCOPE_ZERO_OFFSET_PX)}")
    return True


def bootstrap():
    """เปิดอุปกรณ์ทุกชิ้นทีละขั้นโดยมีจอบูตรายงานความคืบหน้า แล้วคืน TacticalUI"""
    if "--sim" in sys.argv:
        mode, can_fire = "SIM", True
    elif "--webcam" in sys.argv:
        mode, can_fire = "TEST", False
    else:
        mode, can_fire = "LIVE", True

    # เริ่มขาที่ช้าและไม่กิน CPU ไว้ก่อนเลย ให้วิ่งทับกับการโหลดโมเดล
    pre_cam = pre_turret = None
    if mode in ("LIVE", "TEST"):
        import camera
        pre_cam = _prefetch(camera.open_camera)
    if mode == "LIVE":
        import hardware
        pre_turret = _prefetch(hardware.Turret)

    def stage_software(note):
        note("verifying model file")
        tag = config.yolo_model_tag() if config.DETECTOR == "yolo" else "hsv detector"
        note(tag)
        return tag

    def stage_neural(note):
        return detector_mod.get_detector(note)

    def stage_optics(note):
        note("waiting for camera stream")
        cap = _collect(pre_cam)
        note(f"{config.FRAME_WIDTH}x{config.FRAME_HEIGHT}")
        return cap

    def stage_turret(note):
        note("firmata handshake + servo center")
        return _collect(pre_turret)

    def stage_sim(note):
        note("building simulated world")
        import simulator
        return simulator.create_sim()

    def stage_no_turret(note):
        note.warn("test mode - turret bypassed, cannot fire")
        return _NullTurret()

    if mode == "SIM":
        stages = [
            ("SIMULATION CORE", stage_sim),
            # sim วาดเป้าเป็นสีทึบ YOLO มองไม่ออก — ใช้ HSV เหมือนเดิม
            ("TARGET RECOGNITION", lambda note: detector_mod.HsvDetector()),
            ("SAFETY INTERLOCK", _safety_check),
        ]
    else:
        stages = [
            ("FLIGHT SOFTWARE", stage_software),
            ("NEURAL CORE", stage_neural),
            ("OPTICAL SENSOR", stage_optics),
            ("TURRET LINK", stage_turret if mode == "LIVE" else stage_no_turret),
            ("SAFETY INTERLOCK", _safety_check),
        ]

    screen = bootscreen.BootScreen(WINDOW, config.FRAME_WIDTH, config.FRAME_HEIGHT,
                                   subtitle=f"FIRE CONTROL SYSTEM  //  MODE {mode}")
    results = screen.run(stages)

    if mode == "SIM":
        cap, turret = results[0]
        detector = results[1]
    else:
        detector, cap, turret = results[1], results[2], results[3]
    return TacticalUI(cap, turret, detector, mode, can_fire)


def main():
    if "--boot-demo" in sys.argv:      # ดูหน้าตาจอบูตโดยไม่ต้องต่ออุปกรณ์
        bootscreen.demo(WINDOW, config.FRAME_WIDTH, config.FRAME_HEIGHT)
        return 0
    try:
        ui = bootstrap()
    except bootscreen.BootAborted:
        cv2.destroyAllWindows()
        print("[boot] ยกเลิกโดยผู้ใช้")
        return 1
    except Exception as e:
        cv2.destroyAllWindows()
        # ข้อความจริงเป็นภาษาไทย (เช่น คำแนะนำแก้ Camo จอดำใน camera.py) ซึ่งจอ
        # OpenCV วาดไม่ได้ — ต้องมาโผล่ที่ console ให้ครบ (.bat มี pause รออ่านอยู่)
        print(f"\n[boot] เปิดระบบไม่สำเร็จ: {e}\n")
        return 1
    ui.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
