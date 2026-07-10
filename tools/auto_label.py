# =============================================================
# auto_label.py — ใช้โมเดล best.pt ตัวปัจจุบัน "ลาเบลรูปใหม่ให้อัตโนมัติ"
#
# ทำไม: ขี้เกียจลากกรอบเองทีละรูป → ให้โมเดลเดากรอบให้ก่อน แล้วเราแค่
# เข้าไปตรวจ/แก้ใน Roboflow (เร็วกว่าลาเบลจากศูนย์หลายเท่า)
#
# วิธีใช้:
#   venv\Scripts\python.exe tools\auto_label.py <โฟลเดอร์รูปใหม่>
#
# ผลลัพธ์ (สร้างโฟลเดอร์ <ชื่อเดิม>_labeled ข้างๆ):
#   <folder>_labeled\           รูป + ไฟล์ .txt (ลากทั้งโฟลเดอร์นี้เข้า Roboflow ได้เลย
#                               Roboflow จะเห็นว่า "ลาเบลแล้ว" ให้เข้าไปตรวจอย่างเดียว)
#   <folder>_labeled\data.yaml  บอกชื่อคลาสให้ Roboflow ตอน import
#   <folder>_labeled\_preview\  รูปที่วาดกรอบไว้แล้ว — ไล่ดูเร็วๆ ว่าโมเดลตีถูกไหม
#   <folder>_labeled\_no_detection\  รูปที่โมเดลหาไม่เจอเลย → ต้องลาเบลเองใน Roboflow
#
# หมายเหตุ: ใช้ conf ต่ำกว่าตอนรันจริง (0.25) เพราะตอนลาเบล "จับเกินแล้วลบทิ้ง"
# ง่ายกว่า "จับไม่เจอแล้วต้องลากเอง" — กรอบผีที่หลุดมาก็แค่กดลบตอนตรวจ
# =============================================================
import shutil
import sys
from pathlib import Path

import cv2

from _yolo_preview import load_model

LABEL_CONF = 0.25            # ต่ำกว่า YOLO_CONF ตอนรันจริง — เก็บเคสยากๆ (ตัวไกล) มาด้วย
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}   # เทียบแบบ lowercase กันไฟล์ .JPG ตกหล่น


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("วิธีใช้: python tools/auto_label.py <โฟลเดอร์รูปใหม่>")

    src_dir = Path(sys.argv[1])
    if not src_dir.is_dir():
        sys.exit(f"ไม่เจอโฟลเดอร์: {src_dir}")

    images = sorted(p for p in src_dir.iterdir()
                    if p.suffix.lower() in IMAGE_SUFFIXES)
    if not images:
        sys.exit(f"ไม่เจอรูป (.jpg/.jpeg/.png) ใน {src_dir}")

    out_dir = src_dir.parent / f"{src_dir.name}_labeled"
    preview_dir = out_dir / "_preview"
    nodet_dir = out_dir / "_no_detection"
    preview_dir.mkdir(parents=True, exist_ok=True)
    nodet_dir.mkdir(exist_ok=True)

    model = load_model()

    # data.yaml ให้ Roboflow รู้ว่าเลขคลาสไหนคือชื่ออะไรตอน import
    # (ลำดับต้องตรงกับที่โมเดลถูกเทรน: 0=capybara 1=dino 2=elephant)
    names = [model.names[i] for i in range(len(model.names))]
    (out_dir / "data.yaml").write_text(
        f"nc: {len(names)}\nnames: {names}\n", encoding="utf-8")

    n_labeled = n_empty = n_boxes = 0
    for i, img_path in enumerate(images, 1):
        frame = cv2.imread(str(img_path))
        if frame is None:
            print(f"  [{i}/{len(images)}] อ่านรูปไม่ได้ ข้าม: {img_path.name}")
            continue

        results = model.predict(frame, conf=LABEL_CONF, verbose=False)
        boxes = results[0].boxes
        h, w = frame.shape[:2]

        if len(boxes) == 0:
            # โมเดลหาไม่เจอ — แยกไว้ให้ไปลาเบลเองใน Roboflow
            shutil.copy2(img_path, nodet_dir / img_path.name)
            n_empty += 1
            print(f"  [{i}/{len(images)}] {img_path.name}: ไม่เจออะไรเลย → _no_detection")
            continue

        # เขียน label แบบ YOLO: "class cx cy w h" (สัดส่วน 0-1 ของขนาดรูป)
        lines = []
        for box in boxes:
            x1, y1, x2, y2 = map(float, box.xyxy[0])
            cx = (x1 + x2) / 2 / w
            cy = (y1 + y2) / 2 / h
            bw = (x2 - x1) / w
            bh = (y2 - y1) / h
            lines.append(f"{int(box.cls)} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")

            label = model.names[int(box.cls)]
            cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 3)
            cv2.putText(frame, f"{label} {float(box.conf):.0%}",
                        (int(x1), max(25, int(y1) - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

        shutil.copy2(img_path, out_dir / img_path.name)
        (out_dir / f"{img_path.stem}.txt").write_text(
            "\n".join(lines) + "\n", encoding="utf-8")
        cv2.imwrite(str(preview_dir / img_path.name), frame)
        n_labeled += 1
        n_boxes += len(boxes)
        print(f"  [{i}/{len(images)}] {img_path.name}: {len(boxes)} กรอบ")

    print()
    print(f"เสร็จแล้ว → {out_dir}")
    print(f"  ลาเบลให้แล้ว : {n_labeled} รูป ({n_boxes} กรอบ)")
    print(f"  หาไม่เจอ     : {n_empty} รูป (อยู่ใน _no_detection ต้องลาเบลเอง)")
    print()
    print("ขั้นต่อไป:")
    print("  1) เปิดดู _preview เร็วๆ ว่ากรอบส่วนใหญ่ถูกไหม")
    print("  2) ลากโฟลเดอร์ _labeled เข้า Roboflow (Upload) — มันจะอ่าน .txt เป็น label ให้เอง")
    print("  3) ใน Roboflow กดไล่ตรวจ: ลบกรอบผี / ขยับกรอบเบี้ยว / ลาเบลรูปใน _no_detection")
    print("  4) รูปฉากหลังที่ไม่มีตุ๊กตา ให้กด Mark Null (ช่วยลดกรอบผีตอนเทรนรอบใหม่)")


if __name__ == "__main__":
    main()
