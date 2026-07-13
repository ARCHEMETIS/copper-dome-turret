# =============================================================
# main_click.py — จอมอนิเตอร์ยุทธวิธี (OpenCV ล้วน) สำหรับวันแข่ง
#   ธีมทหารสีเขียว มีเส้น/จุดเล็งกลางจอ + กรอบล็อกเป้าแบบเครื่องบินรบ
#   คลิกที่ตัวเป้าเพื่อล็อก → กด F → ป้อมหันไปเล็ง วัดระยะ แล้วยิง
#
# รันกับของจริง:  venv\Scripts\python.exe src\main_click.py
# รันโหมดจำลอง:   venv\Scripts\python.exe src\main_click.py --sim
#
# ปุ่ม:  คลิกซ้าย = เลือก/ล็อกเป้า | คลิกขวา = ปลดล็อก
#        F = ยิงเป้าที่ล็อก | Q หรือ ESC = ออก
#
# ทำไม OpenCV ล้วน (ไม่ใช่ Tkinter แบบ main.py): โจทย์วันจริงคือ "คลิกตัวไหน
# ป้อมหันไปตัวนั้น" ต้อง hit-test คลิกกับกล่อง detection บนภาพโดยตรง —
# แสดงภาพเต็มความละเอียด (ไม่ย่อ) พิกัดคลิกจึงตรงกับพิกัดเฟรม 1:1
# =============================================================
import sys
import threading
import time

import cv2

import aiming
import config
import detector as detector_mod
import ranging

# ---------- สีธีม (BGR) ----------
GREEN = (80, 255, 80)        # เขียว HUD หลัก
GREEN_DIM = (40, 130, 40)    # เขียวจาง — chrome/เส้นรอง
AMBER = (0, 200, 255)        # เหลืองอำพัน — เป้าที่ล็อก (ให้เด่นออกจากตัวอื่น)
RED = (60, 60, 255)          # แดง — เตือน/ยิง
FONT = cv2.FONT_HERSHEY_DUPLEX


class _NullTurret:
    """ป้อมหลอกสำหรับโหมด --webcam: ดูภาพ/คลิกล็อกบนกล้องจริงได้โดยไม่ต้องต่อ
    Arduino — ทุกคำสั่งเป็น no-op (ไม่มีอะไรขยับ/ยิง)"""
    pan_angle = float(config.PAN_CENTER)

    def pan_to(self, angle): pass
    def pan_by(self, delta): pass
    def set_flywheel(self, duty): pass
    def feed_one(self): pass
    def fire(self, duty): pass
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
            # กล้องจริง + โมเดลจริง แต่ไม่ต่อ Arduino — ไว้ทดสอบ detection + HUD
            # + คลิกล็อกบนเว็บแคม (ปุ่ม F ปิดไว้ เพราะไม่มีป้อมให้หัน/ยิง)
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

        self.busy = False            # กำลังเล็ง/ยิง — thread ยิงเป็นคนอ่านกล้อง
        self.locked = None           # label เป้าที่ล็อกไว้ (None = ยังไม่เลือก)
        self.mouse = (0, 0)
        self.dets = []               # detection ล่าสุด (worker เขียน, main thread อ่าน/วาด)
        self._latest = None          # เฟรมล่าสุดที่ส่งให้ worker ตรวจ
        self._alive = False          # ธง life ของ worker thread
        self.status = "READY  //  CLICK A TARGET, PRESS F TO FIRE"
        self.status_color = GREEN

        # เฟรมที่ thread ยิงส่งกลับมาระหว่างเล็ง (main thread เป็นคน imshow เท่านั้น
        # กัน cross-thread GUI พังบางแพลตฟอร์ม)
        self._shared_frame = None
        self._shared_dets = []
        self._lock = threading.Lock()

        self._t0 = time.time()
        self._frames = 0
        self._fps = 0.0

    # ---------- เมาส์ ----------
    def on_mouse(self, event, x, y, flags, _):
        self.mouse = (x, y)
        if self.busy:
            return
        if event == cv2.EVENT_LBUTTONDOWN:
            self._select(x, y)
        elif event == cv2.EVENT_RBUTTONDOWN:
            self.locked = None
            self._set_status("READY  //  CLICK A TARGET, PRESS F TO FIRE", GREEN)

    def _select(self, x, y):
        """เลือกเป้าจากจุดคลิก: ตัวที่คลิกโดนกรอบ (กรอบเล็กสุดชนะถ้าซ้อน)
        ถ้าไม่โดนกรอบไหน เลือกตัวที่ศูนย์กลางใกล้จุดคลิกสุดภายใน 90 px"""
        inside = []
        for d in self.dets:
            if abs(x - d.cx) <= d.w_px / 2 and abs(y - d.cy) <= d.h_px / 2:
                inside.append(d)
        if inside:
            pick = min(inside, key=lambda d: d.w_px * d.h_px)
        else:
            near = [d for d in self.dets
                    if ((x - d.cx) ** 2 + (y - d.cy) ** 2) ** 0.5 <= 90]
            if not near:
                return
            pick = min(near, key=lambda d: (x - d.cx) ** 2 + (y - d.cy) ** 2)
        self.locked = pick.label
        self._set_status(f"TARGET LOCKED: {pick.label.upper()}  //  PRESS F TO FIRE",
                         AMBER)

    # ---------- ยิง ----------
    def start_fire(self):
        if self.busy:
            return
        if not self.can_fire:
            self._set_status("TEST MODE  //  NO TURRET — DETECTION & LOCK ONLY", AMBER)
            return
        if self.locked is None:
            self._set_status("NO TARGET SELECTED  //  CLICK A TARGET FIRST", RED)
            return
        self.busy = True
        threading.Thread(target=self._fire_sequence, args=(self.locked,),
                         daemon=True).start()

    def _fire_sequence(self, target):
        try:
            self._set_status(f"ACQUIRING: {target.upper()} ...", AMBER)

            def on_frame(frame, det):
                with self._lock:
                    self._shared_frame = frame
                    self._shared_dets = [det] if det is not None else []

            det = aiming.aim_at(self.turret, self.cap, self.detector, target, on_frame)
            if det is None:
                self._set_status("NO TARGET / AIM FAILED  //  TRY AGAIN", RED)
                return
            dist = ranging.distance_mm(det)
            duty = ranging.duty_for_distance(dist)
            self._set_status(
                f"RANGE {dist / 1000:.2f} M  >  DUTY {duty:.2f}  |  FIRING", RED)
            self.turret.fire(duty)
            self._set_status(f"SHOT AWAY  //  RANGE {dist / 1000:.2f} M", GREEN)
        except Exception as e:
            self._set_status(f"ERROR: {e}", RED)
        finally:
            self.busy = False

    def _set_status(self, text, color=GREEN):
        self.status, self.status_color = text, color

    # ---------- วาด HUD ----------
    def _draw_reticle(self, img):
        """เส้น + จุดเล็งกลางจอ แบบ boresight เครื่องบินรบ"""
        h, w = img.shape[:2]
        cx, cy = w // 2, h // 2
        gap, arm = 16, 46
        cv2.line(img, (cx - arm, cy), (cx - gap, cy), GREEN, 1)
        cv2.line(img, (cx + gap, cy), (cx + arm, cy), GREEN, 1)
        cv2.line(img, (cx, cy - arm), (cx, cy - gap), GREEN, 1)
        cv2.line(img, (cx, cy + gap), (cx, cy + arm), GREEN, 1)
        cv2.circle(img, (cx, cy), 3, GREEN, -1)           # จุดกลาง
        cv2.circle(img, (cx, cy), 60, GREEN_DIM, 1)       # วงบอกศูนย์
        # ขีดบอกสเกลบนวงเล็ง
        for a in (0, 90, 180, 270):
            import math
            dx, dy = int(60 * math.cos(math.radians(a))), int(60 * math.sin(math.radians(a)))
            cv2.line(img, (cx + dx, cy + dy),
                     (cx + int(dx * 1.12), cy + int(dy * 1.12)), GREEN_DIM, 1)

    def _draw_brackets(self, img, d, color, thick, gap):
        """กรอบมุม (corner brackets) รอบเป้า — สไตล์ระบบล็อกเป้า"""
        x1, y1 = int(d.cx - d.w_px / 2), int(d.cy - d.h_px / 2)
        x2, y2 = int(d.cx + d.w_px / 2), int(d.cy + d.h_px / 2)
        L = max(12, int(min(d.w_px, d.h_px) * 0.28))      # ความยาวขามุม
        for (px, py, sx, sy) in ((x1, y1, 1, 1), (x2, y1, -1, 1),
                                  (x1, y2, 1, -1), (x2, y2, -1, -1)):
            px += sx * gap
            py += sy * gap
            cv2.line(img, (px, py), (px + sx * L, py), color, thick)
            cv2.line(img, (px, py), (px, py + sy * L), color, thick)

    def _draw_target(self, img, d, locked, blink):
        color = AMBER if locked else GREEN
        if locked:
            # ล็อก: กรอบเด่น + ขามุมกะพริบ + กากบาทกลางเป้า + ป้าย LOCK
            self._draw_brackets(img, d, color, 2, 6)
            if blink:
                self._draw_brackets(img, d, color, 2, 14)
            cv2.drawMarker(img, (int(d.cx), int(d.cy)), color,
                           cv2.MARKER_CROSS, 22, 1)
            tag = "[ LOCK ]"
        else:
            self._draw_brackets(img, d, color, 1, 4)
            tag = ""
        # ป้ายข้อมูลเป้า
        rng = ""
        try:
            rng = f"  {ranging.distance_mm(d) / 1000:.2f}M"
        except Exception:
            pass
        label = f"{d.label.upper()} {int(d.conf * 100):02d}%{rng} {tag}"
        ly = int(d.cy - d.h_px / 2) - 8
        cv2.putText(img, label, (int(d.cx - d.w_px / 2), max(14, ly)),
                    FONT, 0.5, color, 1, cv2.LINE_AA)

    def _draw_chrome(self, img, blink):
        h, w = img.shape[:2]
        # กรอบมุมจอ
        m, L = 14, 34
        for (px, py, sx, sy) in ((m, m, 1, 1), (w - m, m, -1, 1),
                                  (m, h - m, 1, -1), (w - m, h - m, -1, -1)):
            cv2.line(img, (px, py), (px + sx * L, py), GREEN, 2)
            cv2.line(img, (px, py), (px, py + sy * L), GREEN, 2)

        # แถบบน
        cv2.putText(img, "COPPER DOME // TACTICAL", (m + 8, 32),
                    FONT, 0.6, GREEN, 1, cv2.LINE_AA)
        rec = "* " if blink else "  "
        right = f"{rec}{self.mode}   PAN {self.turret.pan_angle:5.1f}   {self._fps:4.1f} FPS"
        (tw, _), _ = cv2.getTextSize(right, FONT, 0.55, 1)
        cv2.putText(img, right, (w - m - tw - 8, 32), FONT, 0.55, GREEN, 1, cv2.LINE_AA)

        # แถบล่าง = สถานะ
        cv2.line(img, (m, h - 46), (w - m, h - 46), GREEN_DIM, 1)
        cv2.putText(img, self.status, (m + 8, h - 20),
                    FONT, 0.6, self.status_color, 1, cv2.LINE_AA)

    def _tint(self, img):
        """โทนจอมอนิเตอร์: กดแดง/น้ำเงินลงนิดให้อมเขียว
        ใช้ cv2.convertScaleAbs (SIMD ใน C) แทน numpy astype — เบากว่าหลายเท่า
        ทำต่อเฟรม เลยต้องเร็ว ไม่งั้นเป็นคอขวดเองแม้ detect จะแยก thread แล้ว"""
        img[:, :, 0] = cv2.convertScaleAbs(img[:, :, 0], alpha=0.75)   # B ลง 25%
        img[:, :, 2] = cv2.convertScaleAbs(img[:, :, 2], alpha=0.88)   # R ลง 12%

    def render(self, frame, dets):
        img = frame.copy()
        self._tint(img)
        blink = int(time.time() * 2) % 2 == 0
        for d in dets:
            self._draw_target(img, d, d.label == self.locked, blink)
        self._draw_reticle(img)
        self._draw_chrome(img, blink)
        return img

    # ---------- thread ตรวจจับ (แยกจากการแสดงผล) ----------
    def _detect_worker(self):
        """รัน detect_all วนบนเฟรมล่าสุดตลอด แล้วเก็บผลไว้ที่ self.dets
        แยกจากลูปแสดงผล → วิดีโอเล่นเต็มเฟรมเรตไม่ต้องรอ YOLO (~40ms/เฟรม)
        ตอน busy (aim_at อ่านกล้องเอง) พักไว้ กันแย่งเฟรมกัน"""
        while self._alive:
            if self.busy:
                time.sleep(0.02)
                continue
            with self._lock:
                frame = self._latest
            if frame is None:
                time.sleep(0.005)
                continue
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
            while True:
                if self.busy:
                    with self._lock:
                        frame = None if self._shared_frame is None else self._shared_frame.copy()
                        dets = list(self._shared_dets)
                    if frame is None:
                        ok, frame = self.cap.read()
                        if not ok:
                            continue
                else:
                    ok, frame = self.cap.read()
                    if not ok:
                        continue
                    with self._lock:
                        self._latest = frame          # ส่งเฟรมล่าสุดให้ worker ตรวจ
                    dets = self.dets                  # กล่องล่าสุดจาก worker (อาจช้ากว่าเฟรมนิดหน่อย)

                cv2.imshow(win, self.render(frame, dets))

                # นับ FPS
                self._frames += 1
                if time.time() - self._t0 >= 0.5:
                    self._fps = self._frames / (time.time() - self._t0)
                    self._frames, self._t0 = 0, time.time()

                k = cv2.waitKey(1) & 0xFF
                if k in (ord('q'), 27):
                    break
                if k == ord('f'):
                    self.start_fire()
                if cv2.getWindowProperty(win, cv2.WND_PROP_VISIBLE) < 1:
                    break
        finally:
            self._alive = False
            worker.join(timeout=1.0)
            try:
                self.turret.close()
                self.cap.release()
            finally:
                cv2.destroyAllWindows()


if __name__ == "__main__":
    TacticalUI().run()
