# =============================================================
# main_click.py — จอมอนิเตอร์ยุทธวิธี (OpenCV ล้วน) สำหรับวันแข่ง
#   ธีมทหารเขียว + เส้น/จุดเล็งกลางจอ + ระบบล็อกเป้าแบบเครื่องบินรบ
#
# เล็งด้วย "คลิกที่ไหนก็หันไปที่นั่น" — ไม่พึ่ง detection (วันแข่งมุมเงย + โต๊ะบัง
# ท่อนล่างของเป้า โมเดลอาจมองไม่เห็น/กรอบเพี้ยน แต่ตาคนเห็นชัด) กรอบ detection
# เป็นแค่ "ตัวช่วยเล็ง" สีเขียว ป้อมหันเอาพิกเซลที่คลิกมากลางจอ แล้วเป้าจะมาอยู่
# ใต้เป้าเล็งแดงกลางจอ → เลือกระยะ → ยิง
#
# รันกับของจริง:  venv\Scripts\python.exe src\main_click.py
# รันโหมดจำลอง:   venv\Scripts\python.exe src\main_click.py --sim
#
# ปุ่ม:  คลิกซ้าย = หันไปเล็งจุดนั้น | คลิกขวา = ยกเลิกล็อก
#        1/2/3 = ระยะ ใกล้/กลาง/ไกล | C = คืนป้อมกลางลำ
#        F = ยิง | Q หรือ ESC = ออก
# =============================================================
import math
import sys
import threading
import time

import cv2

import config
import detector as detector_mod
import ranging

# ---------- สีธีม (BGR) ----------
GREEN = (80, 255, 80)        # เขียว HUD หลัก
GREEN_DIM = (40, 130, 40)    # เขียวจาง — chrome/เส้นรอง
AMBER = (0, 200, 255)        # เหลืองอำพัน — เตือน/โหมด TEST
RED = (60, 60, 255)          # แดง — เป้าเล็งที่ล็อก/ยิง
FONT = cv2.FONT_HERSHEY_DUPLEX


class _NullTurret:
    """ป้อมหลอกสำหรับโหมด --webcam: ดูภาพ/คลิกบนกล้องจริงได้โดยไม่ต้องต่อ
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

        self.busy = False            # กำลังยิง (หมุนล้อ+ดันลูก) — กันกดยิงซ้อน
        self.armed = False           # คลิกเล็งแล้ว = พร้อมยิง (โชว์เป้าเล็งแดง)
        self.range_key = config.RANGE_DEFAULT
        self.mouse = (0, 0)
        self.dets = []               # detection ล่าสุด (worker เขียน, main อ่าน/วาด)
        self._latest = None          # เฟรมล่าสุดที่ส่งให้ worker ตรวจ
        self._w = config.FRAME_WIDTH
        self._h = config.FRAME_HEIGHT
        self._alive = False
        self._fire_thread = None
        self._lock = threading.Lock()
        self.status = "CLICK A TARGET TO AIM  //  1/2/3 RANGE  //  F TO FIRE"
        self.status_color = GREEN

        self._t0 = time.time()
        self._frames = 0
        self._fps = 0.0

    # ---------- เมาส์: คลิก = เล็ง ----------
    def on_mouse(self, event, x, y, flags, _):
        self.mouse = (x, y)
        if self.busy:
            return
        if event == cv2.EVENT_LBUTTONDOWN:
            self._aim_click(x)
        elif event == cv2.EVENT_RBUTTONDOWN:
            self.armed = False
            self._set_status("CLICK A TARGET TO AIM  //  1/2/3 RANGE  //  F TO FIRE", GREEN)

    def _aim_click(self, x):
        """หมุนป้อมเอาคอลัมน์พิกเซล x มากลางจอ — มุม = atan(offset / FOCAL_PX)
        ไม่ต้องมี detection: ตาคนเห็นเป้า คลิกได้เลย แม้โมเดลมองไม่เห็น
        คลิกซ้ำเพื่อจูนละเอียด (เป้าเข้าใกล้กลางเรื่อยๆ)"""
        if config.FOCAL_PX:
            offset = x - self._w / 2
            angle = math.degrees(math.atan2(offset, config.FOCAL_PX))
            self.turret.pan_by(config.AIM_SIGN * angle * config.CLICK_AIM_GAIN)
        self.armed = True
        self._announce_armed()

    def _announce_armed(self):
        dist = config.RANGE_PRESETS_MM[self.range_key]
        self._set_status(
            f">> LOCKED · RANGE {self.range_key.upper()} {dist / 1000:.1f}M · F TO FIRE <<",
            RED)

    # ---------- ยิง ----------
    def _duty(self):
        dist = config.RANGE_PRESETS_MM[self.range_key]
        return ranging.duty_for_distance(dist), dist

    def start_fire(self):
        if self.busy:
            return
        if not self.can_fire:
            self._set_status("TEST MODE  //  NO TURRET — AIM & LOCK ONLY", AMBER)
            return
        if not self.armed:
            self._set_status("CLICK A TARGET TO AIM FIRST", RED)
            return
        self.busy = True
        self._fire_thread = threading.Thread(target=self._fire_sequence, daemon=True)
        self._fire_thread.start()

    def _fire_sequence(self):
        try:
            duty, dist = self._duty()
            self._set_status(
                f"FIRING · {self.range_key.upper()} {dist / 1000:.1f}M · DUTY {duty:.2f}", RED)
            self.turret.fire(duty)
            self._set_status(f"SHOT AWAY · {self.range_key.upper()} {dist / 1000:.1f}M", GREEN)
        except Exception as e:
            self._set_status(f"ERROR: {e}", RED)
        finally:
            self.busy = False

    def _set_range(self, key):
        self.range_key = key
        if self.armed:
            self._announce_armed()
        else:
            dist = config.RANGE_PRESETS_MM[key]
            self._set_status(f"RANGE SET: {key.upper()} {dist / 1000:.1f}M", GREEN)

    def _set_status(self, text, color=GREEN):
        self.status, self.status_color = text, color

    # ---------- วาด HUD ----------
    def _draw_reticle(self, img, armed, blink):
        """เป้าเล็งกลางจอ — ปกติเขียว (boresight), ตอน armed เป็นล็อกมิสไซล์แดง
        (เป้าที่คลิกถูกหันมาอยู่ตรงนี้ = จุดที่ลูกจะไป)"""
        h, w = img.shape[:2]
        cx, cy = w // 2, h // 2
        if not armed:
            gap, arm = 16, 46
            cv2.line(img, (cx - arm, cy), (cx - gap, cy), GREEN, 1)
            cv2.line(img, (cx + gap, cy), (cx + arm, cy), GREEN, 1)
            cv2.line(img, (cx, cy - arm), (cx, cy - gap), GREEN, 1)
            cv2.line(img, (cx, cy + gap), (cx, cy + arm), GREEN, 1)
            cv2.circle(img, (cx, cy), 3, GREEN, -1)
            cv2.circle(img, (cx, cy), 60, GREEN_DIM, 1)
            return
        # armed = ล็อกมิสไซล์แดง
        phase = time.time() * 7
        pulse = int(6 + 9 * abs(math.sin(phase)))
        for corner in ((0, 0), (w, 0), (0, h), (w, h)):     # เส้นวิ่งเข้าจาก 4 มุมจอ
            cv2.line(img, corner, (cx, cy), (40, 40, 130), 1, cv2.LINE_AA)
        for r, th in ((34, 2), (34 + pulse, 1)):            # กรอบเหลี่ยมเต้น
            cv2.rectangle(img, (cx - r, cy - r), (cx + r, cy + r), RED, th)
        cv2.circle(img, (cx, cy), 14 + pulse, RED, 1, cv2.LINE_AA)
        cv2.drawMarker(img, (cx, cy), RED, cv2.MARKER_DIAMOND, 18, 2)
        cv2.drawMarker(img, (cx, cy), RED, cv2.MARKER_CROSS, 40, 1)
        if blink:
            txt = "v LOCK v"
            (tw, _), _ = cv2.getTextSize(txt, FONT, 0.6, 2)
            cv2.putText(img, txt, (cx - tw // 2, cy - 44), FONT, 0.6, RED, 2, cv2.LINE_AA)

    def _draw_hint(self, img, d):
        """กรอบ detection เป็น "ตัวช่วยเล็ง" สีเขียว — บอกว่าโมเดลเห็นอะไร
        แต่ไม่ใช่ตัวตัดสินการเล็ง (คนคลิกเอง)"""
        x1, y1 = int(d.cx - d.w_px / 2), int(d.cy - d.h_px / 2)
        x2, y2 = int(d.cx + d.w_px / 2), int(d.cy + d.h_px / 2)
        L = max(12, int(min(d.w_px, d.h_px) * 0.28))
        for (px, py, sx, sy) in ((x1, y1, 1, 1), (x2, y1, -1, 1),
                                  (x1, y2, 1, -1), (x2, y2, -1, -1)):
            px += sx * 4
            py += sy * 4
            cv2.line(img, (px, py), (px + sx * L, py), GREEN, 1)
            cv2.line(img, (px, py), (px, py + sy * L), GREEN, 1)
        label = f"{d.label.upper()} {int(d.conf * 100):02d}%"
        cv2.putText(img, label, (x1, max(14, y1 - 8)), FONT, 0.5, GREEN, 1, cv2.LINE_AA)

    def _draw_chrome(self, img, blink):
        h, w = img.shape[:2]
        m, L = 14, 34
        for (px, py, sx, sy) in ((m, m, 1, 1), (w - m, m, -1, 1),
                                  (m, h - m, 1, -1), (w - m, h - m, -1, -1)):
            cv2.line(img, (px, py), (px + sx * L, py), GREEN, 2)
            cv2.line(img, (px, py), (px, py + sy * L), GREEN, 2)

        cv2.putText(img, "COPPER DOME // TACTICAL", (m + 8, 32),
                    FONT, 0.6, GREEN, 1, cv2.LINE_AA)
        rec = "* " if blink else "  "
        dist = config.RANGE_PRESETS_MM[self.range_key]
        right = (f"{rec}{self.mode}   RNG {self.range_key.upper()} {dist / 1000:.1f}M"
                 f"   PAN {self.turret.pan_angle:5.1f}   {self._fps:4.1f} FPS")
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
        for d in dets:
            self._draw_hint(img, d)
        self._draw_reticle(img, self.armed, blink)
        self._draw_chrome(img, blink)
        return img

    # ---------- thread ตรวจจับ (แยกจากการแสดงผล) ----------
    def _detect_worker(self):
        """รัน detect_all บนเฟรมล่าสุด เก็บผลไว้ที่ self.dets เป็น "ตัวช่วยเล็ง"
        แยก thread → วิดีโอเล่นเต็มเฟรมเรตไม่รอ YOLO. ตรวจเฉพาะเฟรมใหม่ (identity)
        กันวน detect เฟรมเดิมกิน CPU เปล่า"""
        last = None
        while self._alive:
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
            while True:
                # กล้องถูกอ่านที่นี่ "ที่เดียว" — ยิงแค่หมุนล้อ/ดันลูก ไม่แตะกล้อง
                # เลยไม่มีปัญหาแย่ง VideoCapture ระหว่าง thread
                ok, frame = self.cap.read()
                if not ok:
                    continue
                self._h, self._w = frame.shape[:2]
                with self._lock:
                    self._latest = frame
                dets = self.dets

                cv2.imshow(win, self.render(frame, dets))

                self._frames += 1
                if time.time() - self._t0 >= 0.5:
                    self._fps = self._frames / (time.time() - self._t0)
                    self._frames, self._t0 = 0, time.time()

                k = cv2.waitKey(1) & 0xFF
                if k in (ord('q'), 27):
                    break
                elif k == ord('f'):
                    self.start_fire()
                elif k == ord('1'):
                    self._set_range("near")
                elif k == ord('2'):
                    self._set_range("mid")
                elif k == ord('3'):
                    self._set_range("far")
                elif k == ord('c'):
                    self.turret.pan_to(config.PAN_CENTER)
                    self.armed = False
                    self._set_status("TURRET CENTERED", GREEN)
                if cv2.getWindowProperty(win, cv2.WND_PROP_VISIBLE) < 1:
                    break
        finally:
            self._alive = False
            if self._fire_thread is not None:
                self._fire_thread.join(timeout=4.0)   # รอจังหวะยิงจบก่อนปิด serial
            worker.join(timeout=1.0)
            try:
                self.turret.close()
                self.cap.release()
            finally:
                cv2.destroyAllWindows()


if __name__ == "__main__":
    TacticalUI().run()
