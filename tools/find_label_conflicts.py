# =============================================================
# find_label_conflicts.py — สแกนหา label ขัดแย้งใน dataset แบบ YOLO
# รัน:  venv\Scripts\python.exe tools\find_label_conflicts.py [โฟลเดอร์dataset]
#       (ไม่ใส่ = dataset/ ของโปรเจค)
#
# ปัญหาที่เคยเจอ (10 ก.ค.): วัตถุเดียวกันถูกตีกรอบซ้อน 2 class (กรอบ dino
# ทับกรอบ elephant/capybara) 10 ไฟล์ — แก้ในเครื่องแล้ว แต่ต้นทาง Roboflow
# ยังไม่แก้ → **รันสคริปต์นี้กับ export ใหม่ทุกครั้ง** ก่อนเอาไปเทรน
# (wayfinder #12) — เจอไฟล์ไหน ให้ไปแก้ใน Roboflow แล้ว export ซ้ำ
#
# เกณฑ์: กรอบต่าง class ที่ IoU > 0.6 = วัตถุเดียวโดนตีสอง class แทบแน่นอน
# =============================================================
import sys
from pathlib import Path

IOU_THRESHOLD = 0.6
NAMES = {0: "capybara", 1: "dino", 2: "elephant"}   # ตาม dataset/data.yaml


def iou(a, b):
    """กล่อง YOLO (cx, cy, w, h) หน่วย normalized"""
    ax1, ay1, ax2, ay2 = a[0]-a[2]/2, a[1]-a[3]/2, a[0]+a[2]/2, a[1]+a[3]/2
    bx1, by1, bx2, by2 = b[0]-b[2]/2, b[1]-b[3]/2, b[0]+b[2]/2, b[1]+b[3]/2
    iw = max(0, min(ax2, bx2) - max(ax1, bx1))
    ih = max(0, min(ay2, by2) - max(ay1, by1))
    inter = iw * ih
    union = a[2]*a[3] + b[2]*b[3] - inter
    return inter / union if union else 0


def main():
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else \
        Path(__file__).resolve().parent.parent / "dataset"
    label_files = sorted(root.rglob("labels/*.txt"))
    if not label_files:
        sys.exit(f"ไม่เจอไฟล์ label ใต้ {root}")

    conflicts = 0
    for lf in label_files:
        boxes = []
        for line in lf.read_text().splitlines():
            parts = line.split()
            if len(parts) >= 5:
                boxes.append((int(parts[0]), tuple(map(float, parts[1:5]))))
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                ci, bi = boxes[i]
                cj, bj = boxes[j]
                if ci != cj and iou(bi, bj) > IOU_THRESHOLD:
                    conflicts += 1
                    rel = lf.relative_to(root)
                    print(f"⚠ {rel}: {NAMES.get(ci, ci)} ทับ {NAMES.get(cj, cj)} "
                          f"(IoU {iou(bi, bj):.2f})")

    print(f"\nสแกน {len(label_files)} ไฟล์: "
          f"{'พบขัดแย้ง ' + str(conflicts) + ' คู่' if conflicts else '✅ สะอาด ไม่พบกรอบต่าง class ซ้อนกัน'}")
    sys.exit(1 if conflicts else 0)


if __name__ == "__main__":
    main()
