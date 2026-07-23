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
#
# ปุ่ม:  คลิกซ้ายที่ตุ๊กตา = ล็อก+หันตาม | คลิกซ้ายที่ว่าง = เล็งจุดนั้น(สำรอง)
#        คลิกขวา = ยกเลิก/หยุดล็อก | I/J/K/L = เลื่อนจุด zero (ตอนคาลิเบรตสโคป)
#        C = คืนป้อมกลางลำ | F = ยิง | Q หรือ ESC = ออก
# =============================================================
import math
import sys
import threading
import time

import cv2

import aiming
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
    def fire(self): pass
    def close(self): pass


class TacticalUI:
    def __init__(self):
        if "--sim" in sys.argv:
            import simulator
            self.cap, self.turret = simulator.create_sim()
            self.detector = detector_mod.HsvDetector()  # sim วาดเป็นสีทึบ YOLO มองไม่ออก
            self.mode = "SIM"
            self.can_fire = True
        elif "--webcam" in sys.argv:
            import camera
            self.cap = camera.open_camera()
            self.turret = _NullTurret()
            self.detector = detector_mod.get_detector()
            self.mode = "TEST"
            self.can_fire = False
        else:
            import camera
            import hardware
            self.cap = camera.open_camera()
            self.turret = hardware.Turret()
            self.detector = detector_mod.get_detector()
            self.mode = "LIVE"
            self.can_fire = True

        self.op = None               # None | "lock" (ป้อมกำลังหันตามตุ๊กตา) | "fire"
        self.locked_label = None     # ชนิดตุ๊กตาที่ล็อก (None = ล็อกแบบพิกเซล/ยังไม่ล็อก)
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
                self._start_lock(toy.label)        # คลิกโดนตุ๊กตา → ล็อก+หันตาม
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
    def _start_lock(self, label):
        self._abort = False
        self.locked_label = label
        self.armed = False
        self.op = "lock"
        self._op_thread = threading.Thread(target=self._lock_sequence,
                                           args=(label,), daemon=True)
        self._op_thread.start()

    def _lock_sequence(self, label):
        try:
            self._set_status(f"ACQUIRING: {label.upper()} ...", AMBER)

            def on_frame(frame, det):
                with self._lock:
                    self._shared_frame = frame
                    self._shared_dets = [det] if det is not None else []

            det = aiming.aim_at(self.turret, self.cap, self.detector, label,
                                on_frame, should_abort=lambda: self._abort)
            if det is None:
                self.locked_label = None
                self._set_status("LOCK FAILED  //  CLICK ANYWHERE ON SCREEN TO AIM", AMBER)
                return
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
            self.turret.pan_by(config.AIM_SIGN * pan * config.CLICK_AIM_GAIN)
            self.turret.tilt_by(-config.AIM_TILT_SIGN * tilt * config.CLICK_AIM_GAIN)
        self.locked_label = None
        self.armed = True
        self._announce_armed("MANUAL")

    def _announce_armed(self, what):
        self._set_status(f">> LOCKED: {what} · ON ZERO · F TO FIRE <<", RED)

    # ---------- ยิง ----------
    def start_fire(self):
        if self.op is not None:
            return
        if not self.can_fire:
            self._set_status("TEST MODE  //  NO TURRET — LOCK & AIM ONLY", AMBER)
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
                self._set_status(
                    f"SPINNING UP {config.FLYWHEEL_SPINUP_S:.1f}s  //  DO NOT DROP YET", AMBER)
                spin_up()
                end = time.time() + config.FLYWHEEL_FEED_WINDOW_S
                while time.time() < end and not self._abort:
                    self._set_status(
                        f">>>  DROP THE BALL NOW  <<<   {end - time.time():3.1f}s LEFT", RED)
                    time.sleep(0.05)
                self.turret.spin_down()
                self._set_status(
                    "CANCELLED — WHEELS STOPPED" if self._abort
                    else "WHEELS STOPPED  //  F FOR NEXT SHOT", GREEN)
            else:
                self._set_status("FIRING", RED)
                self.turret.fire()
                self._set_status("SHOT AWAY", GREEN)
        except Exception as e:
            self._set_status(f"ERROR: {e}", RED)
        finally:
            self.op = None

    # ---------- เลื่อนจุด zero (ตอนคาลิเบรตสโคป — ยิงจริงแล้วขยับจุดให้ทับรอยโดน) ----------
    def _nudge_zero(self, dx, dy):
        config.SCOPE_ZERO_OFFSET_PX[0] += dx
        config.SCOPE_ZERO_OFFSET_PX[1] += dy
        ox, oy = config.SCOPE_ZERO_OFFSET_PX
        # ค่าอยู่แค่ในหน่วยความจำ — จดลง config.py ถึงจะติดถาวร (โชว์ทั้งจอและ console)
        print(f"SCOPE_ZERO_OFFSET_PX = [{ox}, {oy}]   # copy ไปวางใน config.py")
        self._set_status(f"ZERO OFFSET ({ox:+d}, {oy:+d})  //  จดลง config.py ด้วย!", AMBER)

    def _set_status(self, text, color=GREEN):
        self.status, self.status_color = text, color

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

    def _draw_lock(self, img, cx, cy, hw, hh, blink):
        """เป้าเล็งแดงแบบล็อกมิสไซล์ (ไม่มีเส้นตัดจากมุมจอแล้ว — รกตา)
        ครอบกรอบตุ๊กตาที่ล็อก หรือครอบกลางจอ (โหมดพิกเซล)"""
        phase = time.time() * 7
        pulse = int(6 + 9 * abs(math.sin(phase)))
        cv2.rectangle(img, (cx - hw, cy - hh), (cx + hw, cy + hh), RED, 2)
        cv2.rectangle(img, (cx - hw - pulse, cy - hh - pulse),
                      (cx + hw + pulse, cy + hh + pulse), RED, 1)
        cv2.drawMarker(img, (cx, cy), RED, cv2.MARKER_DIAMOND, 18, 2)
        cv2.drawMarker(img, (cx, cy), RED, cv2.MARKER_CROSS, 36, 1)
        if blink:
            txt = "v LOCK v"
            (tw, _), _ = cv2.getTextSize(txt, FONT, 0.6, 2)
            cv2.putText(img, txt, (cx - tw // 2, cy - hh - 14),
                        FONT, 0.6, RED, 2, cv2.LINE_AA)

    def _draw_hint(self, img, d):
        """กรอบ detection = "ตัวช่วยเล็ง" สีเขียว (โมเดลเห็นอะไร ไม่ใช่ตัวตัดสิน)"""
        x1, y1 = int(d.cx - d.w_px / 2), int(d.cy - d.h_px / 2)
        x2, y2 = int(d.cx + d.w_px / 2), int(d.cy + d.h_px / 2)
        L = max(16, int(min(d.w_px, d.h_px) * 0.32))
        for (px, py, sx, sy) in ((x1, y1, 1, 1), (x2, y1, -1, 1),
                                  (x1, y2, 1, -1), (x2, y2, -1, -1)):
            px += sx * 4
            py += sy * 4
            cv2.line(img, (px, py), (px + sx * L, py), GREEN, 2)
            cv2.line(img, (px, py), (px, py + sy * L), GREEN, 2)
        # ป้ายชื่อ+conf บนแถบเข้ม ให้อ่านชัดบนพื้นหลังอะไรก็ได้
        label = f"{d.label.upper()} {int(d.conf * 100):02d}%"
        (tw, th), _ = cv2.getTextSize(label, FONT, 0.55, 1)
        ly = max(th + 8, y1 - 6)
        cv2.rectangle(img, (x1, ly - th - 6), (x1 + tw + 8, ly + 2), (15, 35, 15), -1)
        cv2.putText(img, label, (x1 + 4, ly - 2), FONT, 0.55, GREEN, 1, cv2.LINE_AA)

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

        cv2.line(img, (m, h - 46), (w - m, h - 46), GREEN_DIM, 1)
        cv2.putText(img, self.status, (m + 8, h - 20),
                    FONT, 0.6, self.status_color, 1, cv2.LINE_AA)

    def _tint(self, img):
        """โทนจอมอนิเตอร์อมเขียว — cv2.convertScaleAbs (เร็ว ~6ms/เฟรม)"""
        img[:, :, 0] = cv2.convertScaleAbs(img[:, :, 0], alpha=0.75)   # B ลง 25%
        img[:, :, 2] = cv2.convertScaleAbs(img[:, :, 2], alpha=0.88)   # R ลง 12%

    def render(self, frame, dets):
        img = frame.copy()
        self._tint(img)
        blink = int(time.time() * 2) % 2 == 0

        locked_det = None
        for d in dets:
            if self.locked_label and d.label == self.locked_label:
                locked_det = d            # ตุ๊กตาที่ล็อก — เดี๋ยววาดแดงทับ
            else:
                self._draw_hint(img, d)   # ตัวอื่น = ตัวช่วยเขียว

        manual = self.armed and self.locked_label is None
        if not manual:
            self._draw_reticle(img)       # โชว์ศูนย์กลางไว้เป็นตัวอ้างอิง

        if locked_det is not None:        # ล็อกตุ๊กตา: เป้าแดงเกาะตุ๊กตา
            self._draw_lock(img, int(locked_det.cx), int(locked_det.cy),
                            int(locked_det.w_px / 2) + 6, int(locked_det.h_px / 2) + 6, blink)
        elif manual:                      # ล็อกพิกเซล: เป้าแดงที่จุด zero
            zx, zy = self._zero_px()
            self._draw_lock(img, zx, zy, 34, 34, blink)

        self._draw_chrome(img, blink)
        return img

    # ---------- thread ตรวจจับ (แยกจากการแสดงผล) ----------
    def _detect_worker(self):
        """รัน detect_all บนเฟรมล่าสุด เก็บผลไว้ที่ self.dets เป็น "ตัวช่วยเล็ง"
        ตรวจเฉพาะเฟรมใหม่ (identity) กันวน detect เฟรมเดิมกิน CPU
        พักตอน op=="lock" เพราะ thread ล็อกเป็นเจ้าของกล้องตอนนั้น"""
        last = None
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
            except Exception:
                pass

    # ---------- ลูปหลัก ----------
    def run(self):
        win = "Copper Dome // Tactical"
        cv2.namedWindow(win, cv2.WINDOW_AUTOSIZE)   # AUTOSIZE = 1:1 พิกัดคลิกตรงเฟรม
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
                        continue
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
                    self.turret.pan_to(config.PAN_CENTER)
                    self.turret.tilt_to(config.TILT_CENTER)
                    self.armed = False
                    self.locked_label = None
                    self._set_status("TURRET CENTERED", GREEN)
                if cv2.getWindowProperty(win, cv2.WND_PROP_VISIBLE) < 1:
                    break
        finally:
            self._abort = True
            self._alive = False
            if self._op_thread is not None:
                self._op_thread.join(timeout=4.0)
            worker.join(timeout=1.0)
            try:
                self.turret.close()
                self.cap.release()
            finally:
                cv2.destroyAllWindows()


if __name__ == "__main__":
    TacticalUI().run()
