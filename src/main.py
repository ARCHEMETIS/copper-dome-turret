# =============================================================
# main.py — โปรแกรมหลัก: UI เลือกเป้า + วิดีโอสด + ปุ่มยิง
# รันกับของจริง:  venv\Scripts\python.exe src\main.py
# รันโหมดจำลอง:   venv\Scripts\python.exe src\main.py --sim   (ไม่ต้องมี Arduino/กล้อง)
#
# ลำดับการทำงานตอนกด FIRE:
#   เล็ง (aiming) → วัดระยะ (ranging) → คำนวณมุมเงย → ยิง (hardware)
# =============================================================
import sys
import threading
import tkinter as tk

import cv2
from PIL import Image, ImageTk

import aiming
import camera
import config
import detector as detector_mod
import hardware
import ranging


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Copper Dome — Turret Control")

        if "--sim" in sys.argv:
            import simulator
            self.cap, self.turret = simulator.create_sim()
            root.title("Copper Dome — SIMULATION MODE")
            # sim วาดเป้าเป็นวงรีสีทึบ (ออกแบบคู่กับช่วง HSV ใน config)
            # YOLO เทรนจากรูปถ่ายจริง มองภาพวาดพวกนี้ไม่ออก — ต้องใช้ HSV เสมอในโหมดนี้
            self.detector = detector_mod.HsvDetector()
        else:
            self.cap = camera.open_camera()
            self.turret = hardware.Turret()
            self.detector = detector_mod.get_detector()

        self.busy = False           # กันกดยิงซ้อนระหว่างกำลังเล็ง/ยิง
        self.target = tk.StringVar(value="dino")
        self.last_overlay = None    # detection ล่าสุดไว้วาดกรอบ

        # ---- ซ้าย: ภาพจากกล้อง ----
        self.video_label = tk.Label(root)
        self.video_label.grid(row=0, column=0, rowspan=6, padx=8, pady=8)

        # ---- ขวา: เลือกเป้า + ปุ่มยิง ----
        tk.Label(root, text="เลือกเป้า", font=("", 14, "bold")).grid(row=0, column=1, sticky="w", padx=8)
        for i, (key, t) in enumerate(config.TARGETS.items(), start=1):
            tk.Radiobutton(root, text=t["display"], value=key, variable=self.target,
                           font=("", 12)).grid(row=i, column=1, sticky="w", padx=16)

        self.fire_btn = tk.Button(root, text="🔥 FIRE", font=("", 16, "bold"),
                                  bg="#c62828", fg="white", width=12,
                                  command=self.on_fire)
        self.fire_btn.grid(row=4, column=1, padx=8, pady=12)

        self.status = tk.Label(root, text="พร้อม", font=("", 11), fg="gray")
        self.status.grid(row=5, column=1, padx=8, sticky="w")

        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.update_video()

    # ---------- วิดีโอสด ----------
    def update_video(self):
        if not self.busy:  # ระหว่างเล็ง thread ยิงเป็นคนอ่านกล้องแทน
            ok, frame = self.cap.read()
            if ok:
                self.show_frame(frame, self.last_overlay)
        self.root.after(33, self.update_video)  # ~30 fps

    def show_frame(self, frame, det=None):
        if det is not None:
            x1 = int(det.cx - det.w_px / 2); y1 = int(det.cy - det.h_px / 2)
            x2 = int(det.cx + det.w_px / 2); y2 = int(det.cy + det.h_px / 2)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, det.label, (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        # เส้นเล็งกลางภาพ
        h, w = frame.shape[:2]
        cv2.line(frame, (w // 2, 0), (w // 2, h), (0, 0, 255), 1)

        frame = cv2.resize(frame, (640, 360))
        img = ImageTk.PhotoImage(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
        self.video_label.configure(image=img)
        self.video_label.image = img  # กัน garbage collect

    # ---------- ยิง ----------
    def on_fire(self):
        if self.busy:
            return
        self.busy = True
        self.fire_btn.config(state="disabled")
        threading.Thread(target=self.fire_sequence, daemon=True).start()

    def fire_sequence(self):
        target = self.target.get()
        try:
            self.set_status(f"กำลังเล็ง: {config.TARGETS[target]['display']} ...")

            def on_frame(frame, det):
                self.last_overlay = det
                self.root.after(0, self.show_frame, frame.copy(), det)

            det = aiming.aim_at(self.turret, self.cap, self.detector, target, on_frame)
            if det is None:
                self.set_status("❌ หาเป้าไม่เจอ / เล็งไม่สำเร็จ")
                return

            dist = ranging.distance_mm(det)
            angle = ranging.angle_for_distance(dist)
            self.set_status(f"ระยะ {dist / 1000:.2f} m → มุมเงย {angle:.0f}° | กำลังยิง...")
            self.turret.fire(angle)
            self.set_status(f"✅ ยิงแล้ว (ระยะ {dist / 1000:.2f} m)")
        except Exception as e:
            self.set_status(f"⚠️ {e}")
        finally:
            self.busy = False
            self.root.after(0, lambda: self.fire_btn.config(state="normal"))

    def set_status(self, text):
        self.root.after(0, lambda: self.status.config(text=text))

    def on_close(self):
        try:
            self.turret.close()
            self.cap.release()
        finally:
            self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
