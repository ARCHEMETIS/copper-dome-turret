# =============================================================
# resplit_dataset.py — แบ่ง train/valid/test ใหม่แบบ "จัดกลุ่มตามคลิปต้นทาง"
#
# ปัญหาที่แก้: รูปที่ตัดมาจากวิดีโอเดียวกัน (เช่น IMG_3481_frame_001, _002, ...)
# เกือบจะเหมือนกันทุกพิกเซล ถ้า Roboflow สุ่มแบ่งทีละรูป เฟรมพี่น้องกันจะไป
# กระจายอยู่ทั้ง train และ valid/test พร้อมกัน → โมเดล "เคยเห็น" ฉากเกือบเดียวกัน
# มาก่อนตอนเทรน แล้วมาวัดผลกับฉากนั้นซ้ำ ทำให้ mAP สูงเกินจริง (data leakage)
#
# วิธีแก้: จัดรูปเป็น "กลุ่ม" ตามคลิปต้นทาง (ตัด _frame_NNN และ .rf.<hash> ออก
# จากชื่อไฟล์) แล้วสุ่มแบ่งทั้งกลุ่มไปอยู่ split เดียวกันเสมอ ไม่แยกรูปในกลุ่ม
# เดียวกันไปคนละ split — รูปเดี่ยวๆ ที่ไม่ได้มาจากวิดีโอ (กลุ่มละ 1 รูป) ก็ยัง
# สุ่มแบ่งได้ตามปกติ เพราะไม่มีพี่น้องให้รั่ว
#
# รัน: python tools/resplit_dataset.py
# =============================================================
import random
import re
import shutil
from collections import defaultdict
from pathlib import Path

DATASET = Path(__file__).resolve().parent.parent / "dataset"
SPLITS = ["train", "valid", "test"]
RATIOS = {"train": 0.70, "valid": 0.20, "test": 0.10}
SEED = 57  # เลือกจากการไล่ seed 0-99 เอาอันที่คลาสกระจายใน valid/test สมดุลสุด
           # (seed 0 เผอิญทำให้คลิป dino ใหญ่ๆ ไปกอง train หมด — valid เหลือ dino แค่ 34 กรอบ)

# เลขเฟรมมี 2 แบบตามยุค: "_frame_012" (ชุดเก่า) และ "-0012" (ชุดใหม่ Roboflow
# สไลซ์วิดีโอ เช่น IMG_1702_MOV-0000_jpg.rf.xxx.jpg) — ตัดทั้งคู่ก่อนจับกลุ่ม
GROUP_RE = re.compile(r"^(.*?)(?:_frame_\d+)?(?:-\d+)?(?:_(?:jpe?g|png))?\.rf\.[A-Za-z0-9]+\.jpe?g$", re.IGNORECASE)
# หมายเหตุ: ห้ามเพิ่ม "*.JPG"/"*.JPEG" — Windows filesystem ไม่แยกตัวพิมพ์เล็ก/ใหญ่
# ของนามสกุลไฟล์อยู่แล้ว ใส่ซ้ำจะทำให้ glob เจอไฟล์เดิมซ้ำ 2 รอบ (นับรูปเบิ้ล)
IMAGE_GLOBS = ("*.jpg", "*.jpeg")


def group_key(filename: str) -> str:
    # Roboflow ใส่ " - Copy" ตรงกลางชื่อไฟล์เวลามีการอัปโหลดซ้ำ (ไฟล์เดียวกันเป๊ะ
    # แค่คนละ entry) — ตัดออกก่อนจับกลุ่ม ไม่งั้นไฟล์ซ้ำจะกลายเป็นคนละกลุ่มแล้วเผลอ
    # หลุดไปอยู่คนละ split จากต้นฉบับที่มันก็อปมา (รั่วหนักกว่าเดิมเพราะเหมือนกันเป๊ะ)
    filename = filename.replace(" - Copy", "")
    m = GROUP_RE.match(filename)
    return m.group(1) if m else filename


def main():
    # 1) เก็บทุกคู่ (รูป, label) จากทั้ง 3 split เดิมมารวมเป็นกองเดียว จัดกลุ่มตามคลิป
    groups = defaultdict(list)  # group_key -> [(image_path, label_path), ...]
    for split in SPLITS:
        img_dir = DATASET / split / "images"
        lbl_dir = DATASET / split / "labels"
        if not img_dir.exists():
            continue
        for pattern in IMAGE_GLOBS:
            for img_path in img_dir.glob(pattern):
                lbl_path = lbl_dir / (img_path.stem + ".txt")
                groups[group_key(img_path.name)].append((img_path, lbl_path))

    total_images = sum(len(v) for v in groups.values())
    print(f"รวม {total_images} รูป จัดเป็น {len(groups)} กลุ่ม (กลุ่มใหญ่สุด 3 อันดับแรก: "
          f"{sorted((len(v) for v in groups.values()), reverse=True)[:3]})")

    # 2) สุ่มลำดับกลุ่ม (seed ตายตัว = ทำซ้ำได้ผลเดิมทุกครั้ง) แล้วไล่ยัดใส่ split
    #    ทีละกลุ่มจนกว่าโควต้ารูปของ split นั้นจะเกือบเต็มตามสัดส่วนที่ตั้งไว้
    rng = random.Random(SEED)
    # ต้อง sort ก่อน shuffle — ไม่งั้นลำดับตั้งต้นขึ้นกับลำดับไฟล์ในโฟลเดอร์
    # ณ ขณะรัน (ซึ่งเปลี่ยนทุกครั้งที่ resplit) แล้ว seed เดิมจะให้ผลไม่เดิม
    group_items = sorted(groups.items())
    rng.shuffle(group_items)

    quota = {s: RATIOS[s] * total_images for s in SPLITS}
    assigned = {s: [] for s in SPLITS}
    counts = {s: 0 for s in SPLITS}

    for gkey, items in group_items:
        # เลือก split ที่ยัง "ขาดโควต้า" มากที่สุด (เทียบเป็นสัดส่วน) ให้กลุ่มนี้ไป
        split = max(SPLITS, key=lambda s: quota[s] - counts[s])
        assigned[split].append((gkey, items))
        counts[split] += len(items)

    # 3) ล้างโฟลเดอร์เดิม แล้วย้ายไฟล์ไปที่ split ใหม่ตามกลุ่มที่จัดไว้
    for split in SPLITS:
        img_dir = DATASET / split / "images"
        lbl_dir = DATASET / split / "labels"
        img_dir.mkdir(parents=True, exist_ok=True)
        lbl_dir.mkdir(parents=True, exist_ok=True)

    # ย้ายเข้าโฟลเดอร์ชั่วคราวก่อน กันกรณีรูปจาก split เดิมทับกับ split ปลายทางเดิม
    tmp_dir = DATASET / "_resplit_tmp"
    for split in SPLITS:
        (tmp_dir / split / "images").mkdir(parents=True, exist_ok=True)
        (tmp_dir / split / "labels").mkdir(parents=True, exist_ok=True)
        for gkey, items in assigned[split]:
            for img_path, lbl_path in items:
                shutil.copy2(img_path, tmp_dir / split / "images" / img_path.name)
                if lbl_path.exists():
                    shutil.copy2(lbl_path, tmp_dir / split / "labels" / lbl_path.name)

    for split in SPLITS:
        shutil.rmtree(DATASET / split)
        shutil.move(str(tmp_dir / split), str(DATASET / split))
    tmp_dir.rmdir()

    # 4) รายงานผล + เช็คว่าไม่มีกลุ่มไหนหลุดไปอยู่มากกว่า 1 split
    print("\nผลการแบ่งใหม่:")
    for split in SPLITS:
        print(f"  {split}: {counts[split]} รูป ({len(assigned[split])} กลุ่ม)")

    seen_in = defaultdict(set)
    for split in SPLITS:
        for gkey, _ in assigned[split]:
            seen_in[gkey].add(split)
    leaked = {g: s for g, s in seen_in.items() if len(s) > 1}
    if leaked:
        print(f"\n⚠️ ยังมีกลุ่มรั่วอยู่ {len(leaked)} กลุ่ม: {leaked}")
    else:
        print("\n✅ ไม่มีกลุ่มไหนซ้ำข้าม split แล้ว")


if __name__ == "__main__":
    main()
