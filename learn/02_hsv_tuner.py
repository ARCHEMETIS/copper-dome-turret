# =============================================================
# บทที่ 2 — HSV Tuner: หา "ช่วงสี" ของวัตถุด้วยแถบเลื่อน
# รัน:  venv\Scripts\python.exe learn\02_hsv_tuner.py
#
# สิ่งที่จะได้เรียนรู้:
#   - ทำไมแยกสีด้วย HSV ไม่ใช่ RGB: ใน HSV "สี" (H) แยกออกจาก "ความสว่าง" (V)
#     → แสงเปลี่ยน สีเพี้ยนน้อยกว่า RGB มาก
#   - H = เนื้อสี 0-179 (แดง~0, เขียว~60, น้ำเงิน~120)
#     S = ความสดของสี 0-255 (ต่ำ = ซีด/ขาว/เทา)
#     V = ความสว่าง 0-255 (ต่ำ = มืด/ดำ)
#   - "mask" = ภาพขาวดำที่ขาว = pixel ที่อยู่ในช่วงสีที่เลือก
#
# วิธีเล่น: เอาวัตถุสีสด (ขวดน้ำ, ฝาขวด, ผลไม้) มาถือหน้ากล้อง
# แล้วเลื่อนแถบจนหน้าต่าง mask เหลือ "ขาวเฉพาะวัตถุ" พื้นหลังดำสนิท
# → ค่าที่ได้เอาไปใช้ในบทที่ 3 (และภายหลังคือค่าของไดโนเสาร์เขียวใน config.py จริง!)
# =============================================================
import cv2
import numpy as np

cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
if not cap.isOpened():
    raise SystemExit("เปิดกล้องไม่ได้ — ลองเปลี่ยน index")

cv2.namedWindow("tuner")
# ค่าเริ่มต้นคือช่วง "สีเขียว" — เลื่อนเองได้เต็มที่
for name, val, mx in [("H min", 35, 179), ("H max", 85, 179),
                      ("S min", 80, 255), ("S max", 255, 255),
                      ("V min", 60, 255), ("V max", 255, 255)]:
    cv2.createTrackbar(name, "tuner", val, mx, lambda x: None)

print("เลื่อนแถบจน mask ขาวเฉพาะวัตถุ | กด p = พิมพ์ค่าออกมา | q = ออก")

while True:
    ok, frame = cap.read()
    if not ok:
        break

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    lo = np.array([cv2.getTrackbarPos(f"{c} min", "tuner") for c in "HSV"])
    hi = np.array([cv2.getTrackbarPos(f"{c} max", "tuner") for c in "HSV"])

    mask = cv2.inRange(hsv, lo, hi)                     # ขาว = อยู่ในช่วงสี
    result = cv2.bitwise_and(frame, frame, mask=mask)   # โชว์เฉพาะส่วนที่ผ่าน mask

    cv2.imshow("tuner", frame)
    cv2.imshow("mask (เป้าหมาย: ขาวเฉพาะวัตถุ)", mask)
    cv2.imshow("result", result)

    key = cv2.waitKey(1) & 0xFF
    if key == ord("q"):
        break
    elif key == ord("p"):
        print(f'"hsv_lower": ({lo[0]}, {lo[1]}, {lo[2]}),')
        print(f'"hsv_upper": ({hi[0]}, {hi[1]}, {hi[2]}),')
        print("↑ รูปแบบเดียวกับใน src/config.py เลย copy ไปใช้ได้")

cap.release()
cv2.destroyAllWindows()

# โจทย์ท้าทาย: ลองจูนหาวัตถุ "สีแดง" ดู — จะพบว่ายาก เพราะสีแดงใน HSV
# อยู่ตรง "รอยต่อ" H=0/179 ต้องใช้ 2 ช่วงรวมกัน นี่คือ quirk ที่ควรรู้ไว้
