# =============================================================
# บทที่ 1 — เปิดกล้อง + เข้าใจว่า "ภาพ" ในคอมคืออะไร
# รัน:  venv\Scripts\python.exe learn\01_camera.py
#
# สิ่งที่จะได้เรียนรู้:
#   - ภาพ 1 เฟรม = ตาราง numpy ขนาด (สูง, กว้าง, 3 สี)
#   - OpenCV เก็บสีเป็น BGR (น้ำเงิน-เขียว-แดง) ไม่ใช่ RGB! จุดนี้คนงงกันเยอะ
#   - loop อ่านกล้อง → วาดทับ → แสดงผล คือโครงของทุกโปรแกรม vision
# =============================================================
import cv2

# ลองเปิดกล้อง index 0 (กล้องโน้ตบุ๊ก) — ถ้าไม่ติดลองเปลี่ยนเป็น 1, 2, ...
# มือถือผ่าน DroidCam/Camo ก็จะโผล่มาเป็น index ตัวใดตัวหนึ่งเหมือนกัน
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
if not cap.isOpened():
    raise SystemExit("เปิดกล้องไม่ได้ — ลองเปลี่ยนเลข index ในบรรทัด VideoCapture")

print("กด s = เซฟภาพ | q = ออก")
snap_count = 0

while True:
    ok, frame = cap.read()          # frame คือ numpy array (H, W, 3) ค่า 0-255
    if not ok:
        break

    h, w = frame.shape[:2]

    # อ่านสีของ pixel ตรงกลางภาพ (สังเกต: ลำดับคือ [แถว, คอลัมน์] = [y, x])
    b, g, r = frame[h // 2, w // 2]

    # วาดทับบนภาพ: กากบาทกลางจอ + ข้อความ
    cv2.line(frame, (w // 2 - 20, h // 2), (w // 2 + 20, h // 2), (0, 0, 255), 2)
    cv2.line(frame, (w // 2, h // 2 - 20), (w // 2, h // 2 + 20), (0, 0, 255), 2)
    cv2.putText(frame, f"center BGR = ({b},{g},{r})  size = {w}x{h}",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    cv2.imshow("Lesson 1 - camera", frame)

    key = cv2.waitKey(1) & 0xFF     # waitKey(1) = รอ 1 ms + จำเป็นต่อการแสดงภาพ
    if key == ord("q"):
        break
    elif key == ord("s"):
        snap_count += 1
        cv2.imwrite(f"snap_{snap_count}.jpg", frame)
        print(f"เซฟ snap_{snap_count}.jpg แล้ว")

cap.release()
cv2.destroyAllWindows()
