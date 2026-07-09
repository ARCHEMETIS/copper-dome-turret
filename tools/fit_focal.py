# =============================================================
# fit_focal.py — หา FOCAL_PX จากชุดรูปที่ถ่ายในระยะที่วัดจริง
#
# ใช้กับโฟลเดอร์ Distance/ ที่ตั้งชื่อไฟล์แบบ:
#   <Class>-<ระยะ>cm-h<สูงจริง cm>-w<กว้างจริง cm>.jpg
#   เช่น  Capybara-100cm-h21-w13.jpg
#
# หลักการ: สูตร pinhole  px = f * ขนาดจริง / ระยะ
#   → รู้ (px จากกรอบ YOLO, ขนาดจริง, ระยะ) หลายๆ รูป ก็ fit หา f ตัวเดียว
#   ด้วย least-squares ผ่านจุดกำเนิด: f = Σ(x·y)/Σ(x²) เมื่อ x = ขนาดจริง/ระยะ
#   แล้วตรวจย้อนกลับว่า f ที่ได้ทำนายระยะพลาดกี่ cm ในแต่ละรูป
#
# วิธีใช้:
#   venv\Scripts\python.exe tools\fit_focal.py Distance
# =============================================================
import re
import sys
from pathlib import Path

import cv2

from _yolo_preview import load_model

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import config

NAME_RE = re.compile(r"(?P<cls>[A-Za-z]+)-(?P<dist>\d+)cm-h(?P<h>\d+)-w(?P<w>\d+)",
                     re.IGNORECASE)
FIT_CONF = 0.25   # conf ต่ำหน่อย — รูปไกลกรอบเล็ก อย่าให้หลุด


def collect_samples(folder: Path, model):
    """อ่านทุกรูป → คืน list ของ (ชื่อ, class, ระยะ_mm, จริง_w_mm, จริง_h_mm, px_w, px_h, img_w)"""
    samples = []
    for p in sorted(folder.glob("*.jpg")):
        m = NAME_RE.match(p.stem)
        if not m:
            print(f"  ข้าม (ชื่อไม่ตรงรูปแบบ): {p.name}")
            continue
        cls = m["cls"].lower()
        dist_mm = int(m["dist"]) * 10
        real_h_mm = int(m["h"]) * 10
        real_w_mm = int(m["w"]) * 10

        img = cv2.imread(str(p))
        if img is None:
            print(f"  ข้าม (อ่านรูปไม่ได้): {p.name}")
            continue

        results = model.predict(img, conf=FIT_CONF, verbose=False)
        # เอากรอบของ class ที่ตรงกับชื่อไฟล์ ตัวที่มั่นใจสุด
        best = None
        for box in results[0].boxes:
            if model.names[int(box.cls)] == cls:
                if best is None or float(box.conf) > float(best.conf):
                    best = box
        if best is None:
            print(f"  ข้าม (YOLO หา {cls} ไม่เจอ): {p.name}")
            continue

        x1, y1, x2, y2 = map(float, best.xyxy[0])
        samples.append((p.name, cls, dist_mm, real_w_mm, real_h_mm,
                        x2 - x1, y2 - y1, img.shape[1]))
    return samples


def fit(samples, use: str):
    """least-squares ผ่านจุดกำเนิด: y = f·x, x = ขนาดจริง/ระยะ, y = px"""
    sxy = sxx = 0.0
    for _, _, dist, rw, rh, pw, ph, _ in samples:
        real, px = (rw, pw) if use == "w" else (rh, ph)
        x = real / dist
        sxy += x * px
        sxx += x * x
    return sxy / sxx


def report(samples, f, use: str):
    print(f"\n===== fit ด้วยความ{'กว้าง' if use == 'w' else 'สูง'}  →  focal = {f:.1f} px =====")
    print(f"{'ไฟล์':38s} {'ระยะจริง':>8s} {'ทำนาย':>8s} {'พลาด':>8s}")
    errs = []
    for name, _, dist, rw, rh, pw, ph, _ in samples:
        real, px = (rw, pw) if use == "w" else (rh, ph)
        pred = f * real / px
        err = pred - dist
        errs.append(abs(err))
        print(f"{name:38s} {dist/10:6.0f}cm {pred/10:6.1f}cm {err/10:+7.1f}cm")
    print(f"  พลาดเฉลี่ย {sum(errs)/len(errs)/10:.1f} cm | แย่สุด {max(errs)/10:.1f} cm")
    return sum(errs) / len(errs)


def fit_effective(samples, f, use: str):
    """ปรับ 'ขนาดผลจริง' รายตัว: ไม้บรรทัดวัดตัวจริง แต่กรอบ YOLO เห็น
    ท่าทาง/หาง/แขนขาไม่เท่ากับที่วัด → fit ขนาดที่ 'กล้องเห็นจริง' ต่อตัว
    จากข้อมูลเลย โดยแต่ละรูปให้ K_i = ระยะ·px แล้วเอา median (ทนรูปหลุด
    โดดๆ ได้ — สำคัญเมื่อมีแค่ 3 รูปต่อตัว) → ขนาดผลจริง = K/f
    สูตร ranging.py เดิมใช้ได้เลย แค่ค่าคงที่ต่อตัวเปลี่ยน"""
    import statistics
    classes = sorted({s[1] for s in samples})
    eff = {}
    for cls in classes:
        sub = [s for s in samples if s[1] == cls]
        ks = [s[2] * _px_of(s, use) for s in sub]
        eff[cls] = statistics.median(ks) / f
    return eff


def _px_of(sample, use: str) -> float:
    """ขนาดกรอบตามมิติที่เลือก: w / h / a (√(w·h) — ทนท่าวางแปลกๆ สุด
    เพราะหมุนตุ๊กตา 90° แล้ว w กับ h สลับกันแต่ผลคูณแทบเท่าเดิม)"""
    pw, ph = sample[5], sample[6]
    if use == "w":
        return pw
    if use == "h":
        return ph
    return (pw * ph) ** 0.5


_DIM_LABEL = {"w": "กว้าง", "h": "สูง", "a": "ขนาด √(กว้าง·สูง)"}


def report_effective(samples, f, eff, use: str):
    dim = _DIM_LABEL[use]
    print(f"\n===== fit ความ{dim}ผลจริงรายตัว (focal = {f:.1f} px) =====")
    for cls in sorted(eff):
        print(f"  {cls:10s} ความ{dim}ผลจริง = {eff[cls]:.0f} mm")
    print(f"{'ไฟล์':38s} {'px':>6s} {'ระยะจริง':>8s} {'ทำนาย':>8s} {'พลาด':>8s}")
    errs = []
    for s in samples:
        name, cls, dist = s[0], s[1], s[2]
        px = _px_of(s, use)
        pred = f * eff[cls] / px
        err = pred - dist
        errs.append(abs(err))
        print(f"{name:38s} {px:6.0f} {dist/10:6.0f}cm {pred/10:6.1f}cm {err/10:+7.1f}cm")
    print(f"  พลาดเฉลี่ย {sum(errs)/len(errs)/10:.1f} cm | แย่สุด {max(errs)/10:.1f} cm")
    return sum(errs) / len(errs)


def main():
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("Distance")
    if not folder.is_dir():
        sys.exit(f"ไม่เจอโฟลเดอร์: {folder}")

    model = load_model()
    samples = collect_samples(folder, model)
    if len(samples) < 3:
        sys.exit(f"รูปใช้ได้แค่ {len(samples)} รูป — น้อยไป fit ไม่น่าเชื่อถือ")

    print(f"ใช้ได้ {len(samples)} รูป  (ความละเอียดรูป: กว้าง {samples[0][7]} px)")

    f_w = fit(samples, "w")
    f_h = fit(samples, "h")
    err_w = report(samples, f_w, "w")
    err_h = report(samples, f_h, "h")

    errs = {}
    effs = {}
    for use in ("w", "h", "a"):
        effs[use] = fit_effective(samples, f_w, use)
        errs[use] = report_effective(samples, f_w, effs[use], use)

    img_w = samples[0][7]
    f_scaled = f_w * config.FRAME_WIDTH / img_w

    print(f"\n===== สรุป =====")
    print(f"พลาดเฉลี่ย (fit รายตัวแล้ว): กว้าง {errs['w']/10:.1f} cm | "
          f"สูง {errs['h']/10:.1f} cm | √(กว้าง·สูง) {errs['a']/10:.1f} cm")
    print("แนะนำใช้ √(กว้าง·สูง) — แม้พลาดบนชุดนี้ใกล้เคียงมิติอื่น แต่ทนท่าวาง")
    print("แปลกๆ (หงายท้อง/ตะแคง/หันเฉียง) ได้ดีสุด เพราะ w↔h สลับกันค่าก็ไม่เปลี่ยน")
    print(f"ค่าที่แนะนำใส่ config:")
    if img_w != config.FRAME_WIDTH:
        print(f"  FOCAL_PX ≈ {f_scaled:.0f}   (สเกลเป็นสตรีม {config.FRAME_WIDTH} px แล้ว)")
    else:
        print(f"  FOCAL_PX = {f_w:.0f}")
    for cls, v in sorted(effs["a"].items()):
        print(f"  real_size_mm ของ {cls}: {v:.0f}")


if __name__ == "__main__":
    main()
