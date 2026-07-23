# =============================================================
# add_negatives.py — เพิ่ม "hard negative" เข้า dataset จากวิดีโอเดียว
#
# ทำไมต้องมี: 23 ก.ค. เจอว่าโมเดลตีถุงพลาสติกเป็น capybara conf 0.83 ทั้งที่
# dataset มี 2,909 รูป — ต้นเหตุคือ negative แคบ (background 6.5% จากการถ่าย
# ครั้งเดียวห้องเดียว) ไม่ใช่ข้อมูลน้อย. เครื่องมือนี้ทำให้ "ถ่ายคลิปห้องใหม่
# 3 นาที → เข้า dataset" เป็นคำสั่งเดียว (ดู docs/vision-baseline.md ข้อ 7)
#
# รัน:  venv\Scripts\python.exe tools\add_negatives.py "คลิป.mp4" --prefix neg3
#       ใส่ --dry-run ก่อนเสมอ: ตัดเฟรม + สแกนหาตุ๊กตาหลุด แต่ยังไม่เขียนลง dataset
#
# ⚠ กฎเหล็ก: เฟรมพวกนี้จะได้ label ว่าง = "ไม่มีเป้าในรูปนี้" ถ้ามีตุ๊กตา
#   หลุดเข้าเฟรมแม้แค่รูปเดียว = สอนโมเดลผิดโดยตรง — ต้องดูภาพที่ --dry-run
#   คัดมาให้ทุกใบก่อนรันจริง
# =============================================================
import argparse
import shutil
import sys
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

PROJECT = Path(__file__).resolve().parent.parent
DATASET = PROJECT / "dataset"
MODEL = PROJECT / "models" / "best.pt"
NAMES = ["capybara", "dino", "elephant"]

BLOCK = 8          # ขนาดบล็อกตอนแบ่ง split (ดูเหตุผลใน split_slot)
DUP_THRESH = 6.0   # mean abs diff ต่ำกว่านี้ = เฟรมแทบไม่ต่างจากอันก่อน (กล้องนิ่ง) → ทิ้ง


def split_slot(index: int) -> str:
    """แบ่ง train/valid/test เป็น "บล็อกต่อเนื่อง" ไม่ใช่สุ่มรายเฟรม

    เฟรมที่ติดกันในวิดีโอหน้าตาเกือบเหมือนกัน ถ้าสุ่มรายเฟรมจะมีเฟรมพี่น้อง
    ไปอยู่คนละ split = data leakage (test ดูดีเกินจริง). บล็อกละ BLOCK เฟรม
    วนรอบละ 9 บล็อก → train 7 / valid 1 / test 1 (~78/11/11)
    """
    slot = (index // BLOCK) % 9
    return "train" if slot <= 6 else ("valid" if slot == 7 else "test")


def slice_video(src: Path, out_dir: Path, prefix: str, stride: int) -> list[Path]:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    cap = cv2.VideoCapture(str(src))
    if not cap.isOpened():
        sys.exit(f"เปิดวิดีโอไม่ได้: {src}")

    kept, dropped, i, prev = [], 0, 0, None
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if i % stride == 0:
            small = cv2.cvtColor(cv2.resize(frame, (96, 54)), cv2.COLOR_BGR2GRAY).astype(np.float32)
            if prev is not None and np.abs(small - prev).mean() < DUP_THRESH:
                dropped += 1
            else:
                p = out_dir / f"{prefix}_{i:05d}.jpg"
                cv2.imwrite(str(p), frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
                kept.append(p)
                prev = small
        i += 1
    cap.release()
    print(f"อ่าน {i} เฟรม → เก็บ {len(kept)} (ทิ้งเฟรมซ้ำ {dropped})")
    return kept


def scan_contamination(frames: list[Path], review_dir: Path, top_n: int) -> None:
    """สแกนด้วยโมเดลปัจจุบันที่ conf ต่ำ แล้วเซฟภาพที่มั่นใจสุดไว้ให้คนดู

    ผลที่ได้อ่านได้ 2 ทาง — ต้องดูภาพเองถึงจะแยกออก:
      • เป็นของในห้อง (ถุง/ผ้า/ผนัง) = false positive → นี่แหละ hard negative ที่อยากได้
      • เป็นตุ๊กตาจริงที่ลืมเก็บออกจากฉาก = ปนเปื้อน → ต้องถ่ายใหม่/ตัดเฟรมนั้นทิ้ง
    """
    from ultralytics import YOLO

    if review_dir.exists():
        shutil.rmtree(review_dir)
    review_dir.mkdir(parents=True)

    model = YOLO(str(MODEL))
    hits, frames_hit = [], {0.20: set(), 0.30: set(), 0.50: set()}
    per_class = {c: Counter() for c in frames_hit}
    for i in range(0, len(frames), 16):
        batch = frames[i:i + 16]
        for p, r in zip(batch, model.predict([str(x) for x in batch], conf=0.10,
                                             imgsz=512, verbose=False)):
            for b in r.boxes:
                cf, cls = float(b.conf), NAMES[int(b.cls)]
                hits.append((cf, cls, p, [float(v) for v in b.xyxy[0]]))
                for c in frames_hit:
                    if cf >= c:
                        frames_hit[c].add(p.name)
                        per_class[c][cls] += 1

    n = len(frames)
    print(f"\n--- FP ของโมเดลปัจจุบันบนคลิปนี้ (ยิ่งสูง = คลิปนี้ยิ่งมีค่า) ---")
    for c in sorted(frames_hit):
        k = len(frames_hit[c])
        print(f"  conf>={c:.2f}: {k:3d}/{n} ({100 * k / n:.1f}%)  {dict(per_class[c])}")

    hits.sort(key=lambda x: -x[0])
    for rank, (cf, cls, p, box) in enumerate(hits[:top_n]):
        img = cv2.imread(str(p))
        x1, y1, x2, y2 = (int(v) for v in box)
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 200, 255), 3)
        cv2.putText(img, f"{cls} {cf:.2f}", (x1, max(20, y1 - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 200, 255), 2)
        cv2.imwrite(str(review_dir / f"{rank:02d}_{cls}_{cf:.2f}_{p.name}"), img)
    print(f"\n👁  เปิดดูให้ครบทุกใบก่อนรันจริง: {review_dir}")
    print("   เห็นตุ๊กตาจริงแม้แค่ใบเดียว = อย่า merge (จะสอนโมเดลผิด)")


def merge(frames: list[Path], manifest_path: Path) -> None:
    counts, manifest = Counter(), []
    for idx, p in enumerate(frames):
        split = split_slot(idx)
        shutil.copy2(p, DATASET / split / "images" / p.name)
        (DATASET / split / "labels" / f"{p.stem}.txt").write_text("")  # ว่าง = background
        counts[split] += 1
        manifest.append(f"{split}/images/{p.name}")
        manifest.append(f"{split}/labels/{p.stem}.txt")
    manifest_path.write_text("\n".join(manifest), encoding="utf-8")

    print(f"\nmerged: {dict(counts)} (รวม {sum(counts.values())})")
    for split in ("train", "valid", "test"):
        lbls = list((DATASET / split / "labels").glob("*.txt"))
        empty = sum(1 for f in lbls if f.stat().st_size == 0)
        print(f"  {split:6s}: {len(lbls):5d} รูป  background {empty:4d} ({100 * empty / len(lbls):.1f}%)")
    print(f"\nถอนคืนได้จาก manifest: {manifest_path}")


def main() -> None:
    ap = argparse.ArgumentParser(description="เพิ่ม hard negative เข้า dataset จากวิดีโอ")
    ap.add_argument("video", type=Path)
    ap.add_argument("--prefix", default="neg", help="คำนำหน้าชื่อไฟล์ (ต้องไม่ซ้ำรอบก่อน — ใช้ถอนคืน/แกะรอยได้)")
    ap.add_argument("--stride", type=int, default=13, help="เก็บ 1 เฟรมทุกกี่เฟรม (13 ≈ 0.43 วิ ที่ 30fps)")
    ap.add_argument("--top", type=int, default=12, help="เซฟภาพ FP มั่นใจสุดกี่ใบไว้ตรวจ")
    ap.add_argument("--dry-run", action="store_true", help="ตัด+สแกนอย่างเดียว ไม่เขียนลง dataset")
    args = ap.parse_args()

    if not args.video.exists():
        sys.exit(f"ไม่พบไฟล์: {args.video}")

    work = PROJECT / "runs" / "negatives" / args.prefix
    frames = slice_video(args.video, work / "frames", args.prefix, args.stride)
    if not frames:
        sys.exit("ไม่ได้เฟรมเลย")
    scan_contamination(frames, work / "review", args.top)

    if args.dry_run:
        print("\n[dry-run] ยังไม่เขียนลง dataset — ตรวจภาพแล้วรันซ้ำโดยไม่ใส่ --dry-run")
        return
    merge(frames, work / "manifest.txt")
    print("\nขั้นต่อไป: เทรนใหม่แล้ววัดตามเกณฑ์ใน docs/vision-baseline.md ข้อ 5 + 7")


if __name__ == "__main__":
    main()
