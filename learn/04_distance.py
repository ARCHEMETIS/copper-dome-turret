# =============================================================
# บทที่ 4 — วัดระยะด้วยกล้องตัวเดียว (ไม่ต้องมีเซนเซอร์ระยะ!)
# รัน:  venv\Scripts\python.exe learn\04_distance.py
#
# หลักการ (อันเดียวกับที่ป้อมจริงใช้เป๊ะ):
#   วัตถุยิ่งไกล → เห็นในภาพยิ่งเล็ก แบบผกผันตรงๆ
#   ระยะ = focal_px × ขนาดจริง ÷ ขนาดในภาพ(px)
#   focal_px หาได้จากการ "calibrate" ครั้งเดียว: วางวัตถุที่ระยะที่รู้ แล้วดูขนาดในภาพ
#
# วิธีเล่น:
#   1) แก้ REAL_WIDTH_MM ให้ตรงกับความกว้างจริงของวัตถุ (วัดด้วยไม้บรรทัด)
#   2) วางวัตถุห่างกล้องระยะที่วัดไว้ เช่น 50 cm → กด c แล้วพิมพ์ 500
#   3) จากนั้นเลื่อนวัตถุเข้า-ออก ดูเลขระยะเปลี่ยนตาม (เอาไม้บรรทัดเช็คได้!)
# =============================================================
import cv2
import numpy as np

# ใช้ HSV เดียวกับบทที่ 2-3 (วัตถุสีเขียว) — เปลี่ยนตามวัตถุที่มี
HSV_LOWER = (35, 80, 60)
HSV_UPPER = (85, 255, 255)
MIN_AREA = 800
REAL_WIDTH_MM = 65.0   # ← ความกว้างจริงของวัตถุ (mm) วัดเองแล้วแก้เลขนี้!

focal_px = None        # ยังไม่ calibrate

cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
if not cap.isOpened():
    raise SystemExit("เปิดกล้องไม่ได้")

print("กด c = calibrate (ต้องรู้ระยะจริงตอนนั้น) | q = ออก")

while True:
    ok, frame = cap.read()
    if not ok:
        break

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array(HSV_LOWER), np.array(HSV_UPPER))
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    w_px = None
    if contours:
        big = max(contours, key=cv2.contourArea)
        if cv2.contourArea(big) >= MIN_AREA:
            x, y, bw, bh = cv2.boundingRect(big)
            w_px = bw
            cv2.rectangle(frame, (x, y), (x + bw, y + bh), (0, 255, 0), 2)
            cv2.putText(frame, f"{bw}px wide", (x, y - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    if focal_px is None:
        msg = "ยังไม่ calibrate - วางวัตถุระยะที่รู้แล้วกด c"
    elif w_px:
        dist_mm = focal_px * REAL_WIDTH_MM / w_px
        msg = f"distance = {dist_mm / 10:.1f} cm"
    else:
        msg = "no target"
    cv2.putText(frame, msg, (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)

    cv2.imshow("Lesson 4 - distance", frame)
    key = cv2.waitKey(1) & 0xFF
    if key == ord("q"):
        break
    elif key == ord("c") and w_px:
        d = float(input("ระยะจริงตอนนี้กี่ mm (เช่น 500): "))
        focal_px = w_px * d / REAL_WIDTH_MM
        print(f"focal_px = {focal_px:.1f}  (ในโปรเจคจริงค่านี้คือ FOCAL_PX ใน config.py)")

cap.release()
cv2.destroyAllWindows()

# สังเกต: ถ้ากล้อง auto-focus ค่า focal จะเปลี่ยนเอง → ระยะเพี้ยน
# นี่แหละคือเหตุผลที่โปรเจคจริงต้อง "ล็อก focus มือถือ" ก่อน calibrate เสมอ!
