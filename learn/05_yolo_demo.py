# =============================================================
# บทที่ 5 — YOLO: AI ตรวจจับวัตถุ 80 ชนิดแบบสำเร็จรูป
# รัน:  venv\Scripts\python.exe learn\05_yolo_demo.py
# (ครั้งแรกจะโหลดโมเดล yolov8n.pt ~6MB อัตโนมัติ ต้องต่อเน็ต)
#
# สิ่งที่จะได้เรียนรู้:
#   - YOLO ต่างจาก HSV ยังไง: HSV ดู "สี" แต่ YOLO เรียนรู้ "รูปร่าง+ลวดลาย"
#     → แยกวัตถุสีจืดๆ ได้ (คาปิบาร่า/ช้างเทาในโปรเจคจริงไง!)
#   - โมเดลสำเร็จรูปรู้จัก 80 อย่าง (คน แก้ว ขวด มือถือ แมว หมา กรรไกร ฯลฯ)
#     ลองหยิบของรอบตัวมาโชว์กล้องดู
#   - ตุ๊กตา 3 ตัวของโปรเจคไม่อยู่ใน 80 ชนิดนี้ → ถึงต้อง "เทรนเอง" ด้วยรูปถ่าย
#     (ขั้นตอนอยู่ใน คู่มือโค้ด-อ่านก่อน.md) แต่โค้ดใช้งานเหมือนไฟล์นี้เป๊ะ
# =============================================================
import cv2
from ultralytics import YOLO

model = YOLO("yolov8n.pt")   # n = nano เล็กสุด เร็วพอสำหรับ CPU

cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
if not cap.isOpened():
    raise SystemExit("เปิดกล้องไม่ได้")

print("หยิบของรอบตัวมาโชว์กล้อง (แก้ว ขวด มือถือ หนังสือ...) | q = ออก")

while True:
    ok, frame = cap.read()
    if not ok:
        break

    # ตรวจจับ 1 เฟรม — conf=0.5 คือ "มั่นใจอย่างน้อย 50% ถึงจะนับ"
    results = model.predict(frame, conf=0.5, verbose=False)

    for box in results[0].boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        name = model.names[int(box.cls)]          # ชื่อ class เช่น "cup"
        conf = float(box.conf)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(frame, f"{name} {conf:.0%}", (x1, y1 - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    cv2.imshow("Lesson 5 - YOLO (q=quit)", frame)
    if (cv2.waitKey(1) & 0xFF) == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()

# ถ้าภาพกระตุก: ปกติบน CPU ได้ ~5-15 fps — โปรเจคจริงพอ เพราะเป้าไม่วิ่งหนี
# เคล็ดลับ: ย่อภาพก่อน predict จะเร็วขึ้น เช่น
#   small = cv2.resize(frame, (640, 360)) แล้ว predict(small)
