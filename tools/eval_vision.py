# =============================================================
# eval_vision.py — ไม้บรรทัดวัด "ความทน" ของโมเดลตรวจจับ (wayfinder #9)
# รัน:  venv\Scripts\python.exe tools\eval_vision.py [model1.pt model2.pt ...]
#       (ไม่ใส่ = ใช้ config.YOLO_MODEL_PATH)
#
# วัด 3 ขา ต่อโมเดล:
#   A) mAP50 / mAP50-95 บน dataset/test (137 รูป, label เวอร์ชันแก้แล้ว)
#      ⚠ เทียบกับเลขเก่าก่อน 10 ก.ค. ไม่ได้ — label ใน test ถูกแก้ไปแล้ว
#   B) ghost rate บน NegativeDataSet/eval (เฟรมจากคลิป negative ดิบ
#      คนละเฟรมกับที่เข้าเทรน แต่ "ฉากเดียวกัน" — ใช้เทียบระหว่างโมเดล/
#      คอนฟิกได้ดี แต่เลขสัมบูรณ์บนฉากใหม่จริงจะแย่กว่านี้ อย่าเอาไปอวด)
#   C) ความเร็ว inference ms/frame บน GPU
#
# เกณฑ์ตัดสิน (จาก docs/vision-baseline.md): รับการเปลี่ยนแปลงเมื่อ
# mAP50 test ไม่ตกเกิน 0.005 และ ghost@0.50 ลดลง (หรือกลับกันโดยไม่แลก)
# =============================================================
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import config  # noqa: E402  (ใช้ default model path)

PROJECT = Path(__file__).resolve().parent.parent
NEG_EVAL_DIR = PROJECT / "NegativeDataSet" / "eval"
DATA_YAML = PROJECT / "dataset" / "data.yaml"
GHOST_CONFS = (0.25, 0.50, 0.65)   # รายงาน ghost หลายระดับ conf ให้เห็นทั้งเส้น


def eval_model(model_path: str) -> dict:
    import cv2
    from ultralytics import YOLO

    model = YOLO(model_path)
    r = {"model": model_path}

    # --- ขา A: mAP บน test ---
    m = model.val(data=str(DATA_YAML), split="test", device=0, verbose=False)
    r["map50"], r["map5095"] = float(m.box.map50), float(m.box.map)

    # --- ขา B: ghost บนเฟรม negative ---
    frames = sorted(NEG_EVAL_DIR.glob("*.jpg"))
    if not frames:
        sys.exit(f"ไม่มีเฟรมใน {NEG_EVAL_DIR} — ดูวิธีสร้างใน docs/vision-baseline.md")
    ghost_frames = {c: 0 for c in GHOST_CONFS}
    ghost_dets = {c: 0 for c in GHOST_CONFS}
    per_class = {c: {} for c in GHOST_CONFS}
    max_conf = 0.0
    times = []
    for f in frames:
        img = cv2.imread(str(f))
        t0 = time.perf_counter()
        res = model.predict(img, conf=0.15, device=0, verbose=False)[0]
        times.append(time.perf_counter() - t0)
        confs = [float(b.conf) for b in res.boxes]
        names = [model.names[int(b.cls)] for b in res.boxes]
        if confs:
            max_conf = max(max_conf, max(confs))
        for c in GHOST_CONFS:
            hits = [n for n, cf in zip(names, confs) if cf >= c]
            if hits:
                ghost_frames[c] += 1
                ghost_dets[c] += len(hits)
                for n in hits:
                    per_class[c][n] = per_class[c].get(n, 0) + 1
    n = len(frames)
    r["neg_frames"] = n
    r["ghost"] = {c: (ghost_frames[c], ghost_frames[c] / n) for c in GHOST_CONFS}
    r["ghost_dets"] = ghost_dets
    r["ghost_class"] = per_class
    r["ghost_max_conf"] = max_conf
    # ขา C: ความเร็ว — ใช้เวลา predict ของขา B (ตัด 5 เฟรมแรกเป็น warmup)
    r["ms_per_frame"] = sum(times[5:]) / len(times[5:]) * 1000
    return r


def main():
    models = sys.argv[1:] or [config.YOLO_MODEL_PATH]
    results = [eval_model(m) for m in models]

    print()
    print(f"{'model':<42}{'mAP50':>7}{'mAP50-95':>10}{'ms/f':>7}", end="")
    for c in GHOST_CONFS:
        print(f"{'ghost@' + f'{c:.2f}':>12}", end="")
    print(f"{'maxconf':>9}")
    for r in results:
        name = Path(r["model"]).name
        print(f"{name:<42}{r['map50']:>7.3f}{r['map5095']:>10.3f}"
              f"{r['ms_per_frame']:>7.1f}", end="")
        for c in GHOST_CONFS:
            cnt, frac = r["ghost"][c]
            print(f"{f'{cnt}/{r['neg_frames']} ({frac:.0%})':>12}", end="")
        print(f"{r['ghost_max_conf']:>9.2f}")
    print()
    for r in results:
        if r["ghost_class"][0.50]:
            print(f"  {Path(r['model']).name} ghost@0.50 แยกตาม class: "
                  f"{r['ghost_class'][0.50]}")


if __name__ == "__main__":
    main()
