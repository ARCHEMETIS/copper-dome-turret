# =============================================================
# บทที่ 3 — ตามวัตถุ + จำลอง "การเล็ง" (เหมือนป้อมจริงแต่ไม่มีมอเตอร์)
# รัน:  venv\Scripts\python.exe learn\03_track_object.py
#
# สิ่งที่จะได้เรียนรู้:
#   - morphology (ลบ noise ออกจาก mask)
#   - contour → กรอบสี่เหลี่ยม → จุดกึ่งกลางวัตถุ
#   - แนวคิด visual servoing: "error = เป้าห่างจากกลางภาพกี่ pixel"
#     ป้อมจริงจะหมุนตาม error นี้ — ที่นี่เราแค่พิมพ์บอกว่าจะหมุนไปทางไหน
#
# ★ นี่คือ logic เดียวกับ src/aiming.py ของโปรเจคจริงแบบย่อส่วน
#   เข้าใจไฟล์นี้ = เข้าใจหัวใจของป้อมทั้งระบบ
# =============================================================
import cv2
import numpy as np

# ← เอาค่าที่จูนได้จากบทที่ 2 มาใส่ตรงนี้ (ค่าเริ่มต้น = สีเขียว)
HSV_LOWER = (35, 80, 60)
HSV_UPPER = (85, 255, 255)
MIN_AREA = 800        # พื้นที่ต่ำสุด (px²) — กรองจุดสีเล็กๆ ที่ไม่ใช่วัตถุจริง
DEADBAND = 25         # ถ้าเป้าห่างกลางภาพไม่เกินนี้ = ถือว่า "เล็งตรงแล้ว"

cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
if not cap.isOpened():
    raise SystemExit("เปิดกล้องไม่ได้")

print("ถือวัตถุสีที่จูนไว้หน้ากล้อง แล้วลองเลื่อนซ้าย-ขวา | q = ออก")

while True:
    ok, frame = cap.read()
    if not ok:
        break
    h, w = frame.shape[:2]
    cx_frame = w // 2

    # --- ขั้น 1: แยกสี (เหมือนบทที่ 2) ---
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array(HSV_LOWER), np.array(HSV_UPPER))

    # --- ขั้น 2: ลบ noise ---
    # OPEN = กัดเม็ดขาวเล็กๆ ทิ้ง | CLOSE = อุดรูดำในก้อนขาว
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    # --- ขั้น 3: หา "ก้อน" ที่ใหญ่สุดใน mask ---
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    status = "no target"
    color = (0, 0, 255)

    if contours:
        big = max(contours, key=cv2.contourArea)
        if cv2.contourArea(big) >= MIN_AREA:
            x, y, bw, bh = cv2.boundingRect(big)
            cx_obj = x + bw // 2

            cv2.rectangle(frame, (x, y), (x + bw, y + bh), (0, 255, 0), 2)
            cv2.circle(frame, (cx_obj, y + bh // 2), 5, (0, 255, 0), -1)

            # --- ขั้น 4: หัวใจของการเล็ง ---
            error = cx_obj - cx_frame   # + = เป้าอยู่ขวาของกลางภาพ
            if abs(error) <= DEADBAND:
                status, color = "ON TARGET! (fire)", (0, 255, 0)
            elif error > 0:
                status, color = f"turn RIGHT ({error:+d}px)", (0, 255, 255)
            else:
                status, color = f"turn LEFT ({error:+d}px)", (0, 255, 255)
            # ป้อมจริง: turret.pan_by(KP * error) — แค่นั้นเอง!

    # เส้นกลางภาพ + โซน deadband
    cv2.line(frame, (cx_frame, 0), (cx_frame, h), (0, 0, 255), 1)
    cv2.rectangle(frame, (cx_frame - DEADBAND, 0), (cx_frame + DEADBAND, h),
                  (0, 0, 255), 1)
    cv2.putText(frame, status, (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2)

    cv2.imshow("Lesson 3 - tracking + aiming", frame)
    cv2.imshow("mask", mask)
    if (cv2.waitKey(1) & 0xFF) == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
