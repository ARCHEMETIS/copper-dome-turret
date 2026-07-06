# =============================================================
# calibrate_focal.py — หาค่า FOCAL_PX ของกล้อง (ทำครั้งเดียวหลังล็อก focus)
#
# ⚠️ สำคัญ: ล็อก focus + exposure ในแอปกล้อง (Camo) ก่อน แล้ว "ห้ามแตะอีก"
#            ถ้า focus เปลี่ยน focal จะเพี้ยน ต้อง calibrate ใหม่
#
# วิธี: 1) วางตุ๊กตาห่างกล้องระยะที่วัดแน่นอน (เช่น 1500 mm วัดด้วยตลับเมตร)
#       2) รันไฟล์นี้ → ลากกรอบครอบตุ๊กตา (ให้พอดีความกว้างที่วัดจริงไว้)
#       3) เอาค่า FOCAL_PX ที่ได้ไปใส่ config.py
# รัน: python tools/calibrate_focal.py
# =============================================================
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import camera


def main():
    dist_mm = float(input("ระยะจริงจากเลนส์ถึงตุ๊กตา (mm) เช่น 1500: "))
    real_w_mm = float(input("ความกว้างจริงของตุ๊กตา (mm) แนวเดียวกับที่กล้องเห็น: "))

    cap = camera.open_camera()
    print("กด SPACE เพื่อ freeze ภาพ แล้วลากกรอบครอบตุ๊กตา, ESC ยกเลิก")
    while True:
        ok, frame = cap.read()
        if not ok:
            continue
        cv2.imshow("preview (SPACE=เลือกกรอบ)", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == 32:  # SPACE
            box = cv2.selectROI("preview (SPACE=เลือกกรอบ)", frame, showCrosshair=True)
            _, _, w_px, _ = box
            if w_px > 0:
                focal = w_px * dist_mm / real_w_mm
                print("\n============================================")
                print(f"  ความกว้างในภาพ = {w_px} px")
                print(f"  FOCAL_PX = {focal:.1f}")
                print(f"  → ไปแก้ config.py:  FOCAL_PX = {focal:.1f}")
                print("============================================")
                # ทดสอบย้อนกลับให้ดูเลยว่าสูตรได้ระยะเดิม
                print(f"  เช็ค: ระยะคำนวณกลับ = {focal * real_w_mm / w_px:.0f} mm (ต้อง ≈ {dist_mm:.0f})")
            break
        elif key == 27:  # ESC
            break
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
