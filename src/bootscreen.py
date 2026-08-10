# =============================================================
# bootscreen.py — จอบูตระบบตอนเปิดโปรแกรม (ธีมศูนย์ควบคุมการยิง)
#
# ทำไมต้องมี: เปิด main_click แล้วต้องรอ 15-25 วิโดยไม่มีอะไรขึ้นจอเลย
# (import torch อย่างเดียวก็ ~10 วิ + โหลดโมเดล + เปิดกล้อง Camo + จับมือ Arduino)
# คนกดแล้วไม่รู้ว่าเครื่องค้างหรือกำลังทำงาน — วันแข่งยิ่งไม่มีเวลามานั่งเดา
#
# หลักการ: งานหนักทั้งหมดไปอยู่บน worker thread ส่วน thread หลักวาดจอ ~50fps
# ระหว่างรอ → เห็นความคืบหน้าจริงทุกวินาที ไม่ใช่ progress bar หลอกที่วิ่งตามเวลา
#
# ใช้หน้าต่างชื่อเดียวกับจอหลัก → พอบูตเสร็จ ภาพกล้องขึ้นแทนที่ในหน้าต่างเดิม
# ไม่มีหน้าต่างเด้งซ้อน
# =============================================================
import threading
import time

import cv2
import numpy as np

GREEN = (80, 255, 80)
GREEN_DIM = (40, 130, 40)
GREEN_FAINT = (26, 74, 26)
AMBER = (0, 200, 255)
RED = (60, 60, 255)
FONT = cv2.FONT_HERSHEY_DUPLEX
MONO = cv2.FONT_HERSHEY_PLAIN

WAIT, RUN, OK, FAIL = range(4)


class BootAborted(Exception):
    """คนกด ESC / ปิดหน้าต่างระหว่างบูต — ไม่ใช่ความผิดพลาดของระบบ"""


def _ascii(text) -> str:
    """ฟอนต์ Hershey ของ OpenCV วาดได้แต่ ASCII — อักขระอื่น (ไทย, em dash)
    ออกมาเป็นกล่องว่าง ข้อความ error จากชั้นล่างเป็นภาษาไทยเกือบทั้งหมด
    จึงต้องกรองก่อนขึ้นจอ (ตัวเต็มภาษาไทยไปโผล่ที่ console แทน)"""
    return str(text).encode("ascii", "replace").decode("ascii")


class _Stage:
    def __init__(self, label, fn):
        self.label = label
        self.fn = fn
        self.state = WAIT
        self.note = ""
        self.warned = False      # ผ่าน แต่มีเรื่องต้องเตือน (เช่น scope zero ยังไม่ตั้ง)
        self.t0 = None
        self.t1 = None

    @property
    def seconds(self):
        if self.t0 is None:
            return None
        return (self.t1 if self.t1 is not None else time.time()) - self.t0


class _Note:
    """ตัวรายงานสถานะย่อยที่ส่งให้ฟังก์ชันของแต่ละขั้นเรียกระหว่างทำงาน

    ใช้:  def stage(note): note("loading weights") ... note.warn("no calibration")
    """

    def __init__(self, stage: _Stage):
        self._stage = stage

    def __call__(self, text):
        self._stage.note = _ascii(text)

    def warn(self, text):
        self._stage.warned = True
        self(text)


class BootScreen:
    def __init__(self, window: str, width: int, height: int,
                 title="COPPER  DOME", subtitle="FIRE CONTROL SYSTEM // ARIS PROJECT III"):
        self.window = window
        self.w = int(width)
        self.h = int(height)
        self.title = title
        self.subtitle = subtitle
        self.stages: list[_Stage] = []
        self._abort = False
        self._log: list[str] = []
        self._t0 = time.time()
        self._base = self._make_base()
        # แถบสแกนที่ไล่ลงจอ — สร้างครั้งเดียว แล้ว cv2.add ทับทีละเฟรม (ถูกกว่าวาดใหม่)
        self._sweep = np.zeros((5, self.w, 3), np.uint8)
        self._sweep[:] = (0, 26, 0)

    # ---------- พื้นหลังคงที่ (วาดครั้งเดียว) ----------
    def _make_base(self):
        img = np.zeros((self.h, self.w, 3), np.uint8)
        img[:, :] = (9, 13, 9)
        img[::3, :] = (9, 24, 9)          # scanline จอ CRT

        m, L = 16, 40                     # กรอบมุม — ชุดเดียวกับจอหลัก
        for (px, py, sx, sy) in ((m, m, 1, 1), (self.w - m, m, -1, 1),
                                 (m, self.h - m, 1, -1), (self.w - m, self.h - m, -1, -1)):
            cv2.line(img, (px, py), (px + sx * L, py), GREEN, 2)
            cv2.line(img, (px, py), (px, py + sy * L), GREEN, 2)

        self._center(img, self.title, 108, FONT, 1.7, GREEN, 2)
        self._center(img, self.subtitle, 146, FONT, 0.6, GREEN_DIM, 1)
        cv2.line(img, (110, 176), (self.w - 110, 176), GREEN_FAINT, 1)
        return img

    def _center(self, img, text, y, font, scale, color, thick):
        (tw, _), _ = cv2.getTextSize(text, font, scale, thick)
        cv2.putText(img, text, ((self.w - tw) // 2, y), font, scale, color,
                    thick, cv2.LINE_AA)

    # ---------- วาดหนึ่งเฟรม ----------
    @staticmethod
    def _tag(stage):
        if stage.state == OK:
            return ("[ WARN ]", AMBER) if stage.warned else ("[  OK  ]", GREEN)
        if stage.state == FAIL:
            return "[ FAIL ]", RED
        if stage.state == RUN:
            spin = ">>>>" [:1 + int(time.time() * 6) % 4]
            return f"[ {spin:<4} ]", AMBER
        return "[      ]", GREEN_FAINT

    def _draw(self):
        img = self._base.copy()

        # แถบสแกนไล่ลง — ให้จอ "มีชีวิต" ระหว่างขั้นที่ค้างนานๆ
        y = int((time.time() * 260) % (self.h + 240)) - 120
        if 0 <= y < self.h - 5:
            img[y:y + 5] = cv2.add(img[y:y + 5], self._sweep)

        elapsed = time.time() - self._t0
        clock = f"T+{int(elapsed // 60):02d}:{elapsed % 60:04.1f}"
        (tw, _), _ = cv2.getTextSize(clock, MONO, 1.3, 1)
        cv2.putText(img, clock, (self.w - 120 - tw, 210), MONO, 1.3, GREEN_DIM, 1, cv2.LINE_AA)
        cv2.putText(img, "SYSTEM BOOT SEQUENCE", (112, 210), MONO, 1.3,
                    GREEN_DIM, 1, cv2.LINE_AA)

        x, y0, dy = 118, 258, 46
        done = 0
        for i, st in enumerate(self.stages):
            yy = y0 + i * dy
            tag, color = self._tag(st)
            cv2.putText(img, tag, (x, yy), MONO, 1.5, color, 1, cv2.LINE_AA)

            dim = GREEN_FAINT if st.state == WAIT else color
            name = f"{st.label} {'.' * max(3, 30 - len(st.label))}"
            cv2.putText(img, name, (x + 116, yy), MONO, 1.5, dim, 1, cv2.LINE_AA)

            if st.seconds is not None:
                secs = f"{st.seconds:5.2f}s"
                (sw, _), _ = cv2.getTextSize(secs, MONO, 1.3, 1)
                cv2.putText(img, secs, (self.w - 118 - sw, yy), MONO, 1.3,
                            dim, 1, cv2.LINE_AA)
            show_note = ((st.note and st.state in (RUN, FAIL))
                         or (st.warned and st.state == OK))
            if show_note:
                cv2.putText(img, st.note[:58], (x + 132, yy + 19), MONO, 1.1,
                            RED if st.state == FAIL else AMBER, 1, cv2.LINE_AA)
            if st.state in (OK, FAIL):
                done += 1

        # แถบความคืบหน้า — นับตามขั้นที่จบจริง ไม่ใช่วิ่งตามเวลาแบบหลอกตา
        running = any(st.state == RUN for st in self.stages)
        frac = (done + (0.4 if running else 0)) / max(1, len(self.stages))
        bx1, bx2 = 118, self.w - 118
        by = y0 + len(self.stages) * dy + 34
        cv2.rectangle(img, (bx1, by), (bx2, by + 22), GREEN_FAINT, 1)
        fill = int((bx2 - bx1 - 6) * min(1.0, frac))
        if fill > 0:
            cv2.rectangle(img, (bx1 + 3, by + 3), (bx1 + 3 + fill, by + 19), GREEN, -1)
        cv2.putText(img, f"{int(frac * 100):3d}%", (bx2 + 12, by + 18), MONO, 1.2,
                    GREEN, 1, cv2.LINE_AA)

        # บรรทัด log ล่างสุด + เคอร์เซอร์กะพริบ
        line = self._log[-1] if self._log else "standby"
        caret = "_" if int(time.time() * 2) % 2 == 0 else " "
        cv2.putText(img, f"> {line}{caret}", (118, by + 66), MONO, 1.3,
                    GREEN_DIM, 1, cv2.LINE_AA)

        hint = "ABORTING AFTER CURRENT STEP ..." if self._abort else "ESC = ABORT"
        self._center(img, hint, self.h - 34, MONO, 1.1,
                     AMBER if self._abort else GREEN_FAINT, 1)
        return img

    def _flash(self, text, color, seconds):
        """ข้อความสรุปตัวใหญ่กลางจอ (ALL SYSTEMS GO / LAUNCH ABORTED)"""
        end = time.time() + seconds
        while time.time() < end:
            img = self._draw()
            cv2.rectangle(img, (0, self.h // 2 - 54), (self.w, self.h // 2 + 26),
                          (0, 0, 0), -1)
            if int(time.time() * 6) % 2 == 0 or seconds > 2:
                self._center(img, text, self.h // 2 + 6, FONT, 1.5, color, 3)
            cv2.imshow(self.window, img)
            if (cv2.waitKey(20) & 0xFF) in (27, ord('q')):
                return

    # ---------- ตัวรัน ----------
    def run(self, stages):
        """รันทีละขั้นพร้อมวาดจอไปด้วย

        stages: [(ชื่อขั้น, fn(note)), ...] — fn คืนค่าอะไรก็ได้ (เก็บให้ในลิสต์ผลลัพธ์)
                และเรียก note("...") ระหว่างทางเพื่อรายงานว่าตอนนี้ทำอะไรอยู่
        คืน: list ผลลัพธ์ของแต่ละขั้นตามลำดับ
        โยน: exception เดิมของขั้นที่พัง / BootAborted ถ้าคนสั่งยกเลิก
        """
        self.stages = [_Stage(label, fn) for label, fn in stages]
        results = []
        error = []

        def worker():
            for st in self.stages:
                if self._abort:
                    return
                st.state = RUN
                st.t0 = time.time()
                self._log.append(st.label.lower())
                try:
                    results.append(st.fn(_Note(st)))
                except BaseException as e:      # noqa: BLE001 — ต้องโชว์ทุกชนิดบนจอ
                    st.t1 = time.time()
                    st.state = FAIL
                    st.note = _ascii(str(e).splitlines()[0] if str(e) else type(e).__name__)
                    error.append(e)
                    return
                st.t1 = time.time()
                st.state = OK
                self._log.append(f"{st.label.lower()} ok ({st.seconds:.2f}s)")

        cv2.namedWindow(self.window, cv2.WINDOW_AUTOSIZE)
        th = threading.Thread(target=worker, daemon=True)
        th.start()
        while th.is_alive():
            cv2.imshow(self.window, self._draw())
            k = cv2.waitKey(20) & 0xFF
            if k in (27, ord('q')):
                # ขั้นที่ค้างอยู่หยุดกลางคันไม่ได้ (บล็อกอยู่ใน C) — ตั้งธงไว้แล้ว
                # ไม่เริ่มขั้นถัดไป จอบอกให้ชัดว่ากำลังจะเลิก คนจะได้ไม่กดซ้ำ
                self._abort = True
            if cv2.getWindowProperty(self.window, cv2.WND_PROP_VISIBLE) < 1:
                self._abort = True
                break
        th.join(timeout=0.5)

        if error:
            self._flash("LAUNCH ABORTED", RED, 3.5)
            raise error[0]
        if self._abort:
            raise BootAborted("ยกเลิกระหว่างบูตระบบ")
        self._flash("ALL SYSTEMS GO", GREEN, 0.9)
        return results


def demo(window="Copper Dome // Tactical", width=1280, height=720):
    """ดูหน้าตาจอบูตโดยไม่ต้องต่ออุปกรณ์:  python src\\main_click.py --boot-demo"""
    def fake(seconds, notes):
        def stage(note):
            for i, text in enumerate(notes):
                note(text)
                time.sleep(seconds / len(notes))
            return None
        return stage

    BootScreen(window, width, height).run([
        ("FLIGHT SOFTWARE", fake(0.8, ["verifying model file", "best.pt@58e7fef4"])),
        ("NEURAL CORE", fake(3.0, ["importing torch + ultralytics", "loading weights",
                                   "device = CUDA", "warming up kernels @ imgsz 512",
                                   "warming up kernels @ imgsz 640"])),
        ("OPTICAL SENSOR", fake(1.4, ["waiting for camera stream", "1280x720 @ MSMF"])),
        ("TURRET LINK", fake(2.0, ["firmata handshake", "servo pan/tilt centered"])),
        ("SAFETY INTERLOCK", fake(0.6, ["wheels stopped", "scope zero loaded"])),
    ])
    time.sleep(0.4)
    cv2.destroyAllWindows()
