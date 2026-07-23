# =============================================================
# test_on_webcam.py — เปิดเว็บแคมจริง รันโมเดล YOLO ที่เทรนแล้วแบบสดๆ
# ในจอมอนิเตอร์ยุทธวิธี (ธีมทหารเขียว + เส้นเล็งกลางจอ + คลิกล็อกเป้า)
# ไม่ต้องมี Arduino / ตุ๊กตาก็ดูได้ว่าโมเดลตรวจจับอะไรได้บ้าง
#
# รัน: python tools/test_on_webcam.py
# คลิกซ้าย = หันไปเล็งจุดนั้น | คลิกขวา = ยกเลิก | q / ESC = ปิดหน้าต่าง
# (โหมดนี้ไม่ต่อป้อม การเล็ง/ยิงเป็น no-op — ไว้ดู detection + HUD บนกล้องจริง
#  ถ้าต่อ Arduino ครบแล้วอยากเล็ง+ยิงจริง ใช้:  python src\main_click.py)
# =============================================================
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import main_click

if __name__ == "__main__":
    if "--webcam" not in sys.argv:
        sys.argv.append("--webcam")   # บังคับโหมดกล้องจริง + ป้อมหลอก (ไม่ต่อ Arduino)
    main_click.TacticalUI().run()

