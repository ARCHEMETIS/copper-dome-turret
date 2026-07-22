# =============================================================
# dedup_images.py — กรองภาพซ้ำ/เกือบซ้ำออกก่อนเอาเข้า dataset
# ใช้ average-hash เทียบความคล้ายภาพ ไม่ต้องลง library เพิ่ม (ใช้ Pillow+numpy ที่มีอยู่แล้ว)
#
# รองรับ 2 แบบ:
#   1) โฟลเดอร์ภาพเปล่าๆ (flat)
#   2) โฟลเดอร์ train/valid/test ที่มี images/ + labels/ ข้างใน (แบบ roboflow export)
#      — สแกนรวมข้าม split ด้วย เพื่อจับ "ภาพซ้ำข้าม train/valid" (data leakage)
#
# รัน:
#   python tools/dedup_images.py <โฟลเดอร์> [--threshold 5] [--move]
#   python tools/dedup_images.py <โฟลเดอร์ใหม่> --against <โฟลเดอร์เดิม> [--threshold 5] [--move]
#
# --against : เทียบกับ dataset เดิมด้วย (เช่นเพื่อนเอา dataset เดิมไปผสมกลับมา)
#             ภาพใน --against จะไม่ถูกย้าย ใช้เป็นฐานเทียบอย่างเดียว
#
# ค่าเริ่มต้น: แค่รายงานว่าภาพไหนซ้ำกับภาพไหน ไม่ลบ/ย้ายอะไร
# --move : ย้ายภาพ (+label คู่กันถ้ามี) ที่ซ้ำไปโฟลเดอร์ย่อย _duplicates/ ให้ตรวจซ้ำด้วยตาก่อนลบจริง
# =============================================================
import argparse
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HASH_SIZE = 8  # 8x8 = 64-bit hash
IMG_EXTS = {".jpg", ".jpeg", ".png"}


def average_hash(path: Path) -> np.ndarray:
    img = Image.open(path).convert("L").resize((HASH_SIZE, HASH_SIZE), Image.LANCZOS)
    arr = np.asarray(img, dtype=np.float64)
    return arr > arr.mean()


def hamming(a: np.ndarray, b: np.ndarray) -> int:
    return int(np.count_nonzero(a != b))


def label_path_for(img_path: Path) -> Path | None:
    """หา label .txt คู่กัน ถ้าภาพอยู่ใน .../images/ ให้หาใน .../labels/"""
    if img_path.parent.name == "images":
        candidate = img_path.parent.parent / "labels" / (img_path.stem + ".txt")
        return candidate if candidate.exists() else None
    return None


def find_images(root: Path) -> list[Path]:
    # แบบ split: root/{train,valid,test}/images/*
    split_dirs = list(root.glob("*/images"))
    if split_dirs:
        files = []
        for d in split_dirs:
            files += sorted(p for p in d.iterdir() if p.suffix.lower() in IMG_EXTS)
        return files
    # แบบ flat
    return sorted(p for p in root.iterdir() if p.suffix.lower() in IMG_EXTS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", type=Path, help="โฟลเดอร์ภาพที่จะกรอง (flat หรือ train/valid/test)")
    ap.add_argument("--against", type=Path, nargs="*", default=[],
                     help="โฟลเดอร์ dataset เดิมที่จะเทียบด้วย (ภาพในนี้จะไม่ถูกย้าย ใช้เป็นฐานเทียบอย่างเดียว)")
    ap.add_argument("--threshold", type=int, default=5,
                     help="bit ต่างกันไม่เกินเท่านี้ถือว่าซ้ำ (0-64, ยิ่งน้อยยิ่งเข้มงวด, default=5)")
    ap.add_argument("--move", action="store_true",
                     help="ย้ายภาพซ้ำ (+label คู่กัน) ไป _duplicates/ แทนแค่รายงาน")
    args = ap.parse_args()

    files = find_images(args.folder)
    if not files:
        print(f"ไม่เจอภาพใน {args.folder}")
        sys.exit(1)

    ref_files = []
    for ref_root in args.against:
        ref_files += find_images(ref_root)

    print(f"กำลังคำนวณ hash ของ {len(files)} ภาพ (รวมทุก split)"
          + (f" + {len(ref_files)} ภาพจาก dataset เดิม" if ref_files else "") + "...")

    def hash_all(paths):
        out = []
        for i, p in enumerate(paths, 1):
            try:
                out.append((p, average_hash(p)))
            except Exception as e:
                print(f"  ข้าม {p.name}: {e}")
            if i % 200 == 0:
                print(f"  ...{i}/{len(paths)}")
        return out

    hashes = hash_all(files)
    ref_hashes = hash_all(ref_files) if ref_files else []

    # ภาพเดิม (--against) ทั้งหมดถือเป็น "kept" อยู่แล้วตั้งแต่ต้น เทียบภาพใหม่กับมันได้ แต่ไม่ย้ายมันเอง
    kept = list(ref_hashes)
    n_ref_kept = len(kept)
    dropped = []
    for path, h in hashes:
        is_dup = False
        for kept_path, kept_h in kept:
            if hamming(h, kept_h) <= args.threshold:
                is_dup = True
                vs_ref = kept_path in [rp for rp, _ in ref_hashes]
                same_split = (not vs_ref) and path.parent.parent.name == kept_path.parent.parent.name
                dropped.append((path, kept_path, same_split, vs_ref))
                break
        if not is_dup:
            kept.append((path, h))
    new_kept = len(kept) - n_ref_kept

    vs_original = [d for d in dropped if d[3]]
    cross_split = [d for d in dropped if not d[3] and not d[2]]
    print(f"\nเก็บใหม่ {new_kept} ภาพ / ซ้ำ {len(dropped)} ภาพ "
          f"(ซ้ำกับ dataset เดิมโดยตรง {len(vs_original)} ภาพ, "
          f"ซ้ำข้าม split ภายในตัวเอง {len(cross_split)} ภาพ)")

    if dropped:
        print("ตัวอย่างคู่ที่ซ้ำกัน (แสดง 10 คู่แรก):")
        for path, matched, same_split, vs_ref in dropped[:10]:
            if vs_ref:
                tag = "  [ซ้ำกับ dataset เดิม!]"
            elif not same_split:
                tag = "  [ข้าม split!]"
            else:
                tag = ""
            print(f"  {path.parent.parent.name}/{path.name}  ~=  {matched.parent.parent.name}/{matched.name}{tag}")

    if args.move and dropped:
        dup_dir = args.folder / "_duplicates"
        dup_dir.mkdir(exist_ok=True)
        for path, _, _, _ in dropped:
            shutil.move(str(path), str(dup_dir / path.name))
            lbl = label_path_for(path)
            if lbl:
                shutil.move(str(lbl), str(dup_dir / lbl.name))
        print(f"\nย้าย {len(dropped)} ภาพซ้ำ (+label คู่กัน) ไปไว้ที่ {dup_dir} แล้ว (ตรวจซ้ำด้วยตาก่อนลบทิ้งจริง)")
    elif dropped:
        print("\n(รันด้วย --move เพื่อย้ายภาพซ้ำออกไปที่ _duplicates/ ให้ตรวจก่อนลบจริง)")


if __name__ == "__main__":
    main()
