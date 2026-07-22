# =============================================================
# eval_vision.py — ไม้บรรทัดวัด "ความทน" ของโมเดลตรวจจับ (wayfinder #9)
# รัน:  venv\Scripts\python.exe tools\eval_vision.py [model1.pt model2.pt ...]
#       (ไม่ใส่ = ใช้ config.YOLO_MODEL_PATH)
#
# วัด 3 ขา ต่อโมเดล:
#   A) mAP50 / mAP50-95 บน dataset/test (280 รูป, label เวอร์ชันแก้แล้ว)
#      ⚠ เทียบกับเลขเก่าก่อน 10 ก.ค. ไม่ได้ — label ใน test ถูกแก้ไปแล้ว
#   B) ghost rate บน NegativeDataSet/eval (เฟรมจากคลิป negative ดิบ
#      คนละเฟรมกับที่เข้าเทรน แต่ "ฉากเดียวกัน" — ใช้เทียบระหว่างโมเดล/
#      คอนฟิกได้ดี แต่เลขสัมบูรณ์บนฉากใหม่จริงจะแย่กว่านี้ อย่าเอาไปอวด)
#   C) ความเร็ว inference ms/frame บน GPU
#
# เกณฑ์ตัดสิน (จาก docs/vision-baseline.md): รับการเปลี่ยนแปลงเมื่อ
# mAP50 test ไม่ตกเกิน 0.005 และ ghost@0.50 ลดลง (หรือกลับกันโดยไม่แลก)
# =============================================================
import argparse
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import config  # noqa: E402  (ใช้ default model path)

PROJECT = Path(__file__).resolve().parent.parent
NEG_EVAL_DIR = PROJECT / "NegativeDataSet" / "eval"
TEST_IMAGES_DIR = PROJECT / "dataset" / "test" / "images"
DATA_YAML = PROJECT / "dataset" / "data.yaml"
GHOST_CONFS = (0.25, 0.30, 0.50, 0.65)   # รวม 0.30 = จุดทำงานจริง (config.YOLO_CONF); หลายระดับให้เห็นทั้งเส้น
BENCH_WARMUP = 20
BENCH_RUNS = 200


def eval_model(model_path: str, imgsz=None, device=0, bench=False) -> dict:
    import cv2
    from ultralytics import YOLO

    model = YOLO(model_path)
    r = {"model": model_path}
    if imgsz is not None:
        r["imgsz"] = imgsz

    # --- ขา A: mAP บน test ---
    val_args = {"data": str(DATA_YAML), "split": "test", "device": device,
                "verbose": False, "workers": 2}  # workers=2 บังคับ: กัน RuntimeError 1455 (Windows shared-mem) ที่ default 8
    if imgsz is not None:
        val_args["imgsz"] = imgsz
    m = model.val(**val_args)
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
        predict_args = {"conf": 0.15, "device": device, "verbose": False}
        if imgsz is not None:
            predict_args["imgsz"] = imgsz
        t0 = time.perf_counter()
        res = model.predict(img, **predict_args)[0]
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
    # ขา C เดิม: ใช้เวลา predict ของขา B (ตัด 5 เฟรมแรกเป็น warmup)
    r["ms_per_frame"] = sum(times[5:]) / len(times[5:]) * 1000
    if bench:
        r["bench_median_ms"], r["bench_p90_ms"] = benchmark_model(
            model, imgsz, device, cv2
        )
    return r


def benchmark_model(model, imgsz: int, device, cv2) -> tuple[float, float]:
    """Benchmark already-loaded real images; only synchronous predict is timed."""
    # A small fixed real-image set avoids timing storage/decode effects and is
    # cycled enough times to expose inference variance.
    image_paths = sorted(TEST_IMAGES_DIR.glob("*"))[:3]
    images = [cv2.imread(str(path)) for path in image_paths if path.is_file()]
    images = [image for image in images if image is not None]
    if not images:
        sys.exit(f"ไม่มีรูป benchmark ใน {TEST_IMAGES_DIR}")

    predict_args = {"imgsz": imgsz, "device": device, "verbose": False}
    for i in range(BENCH_WARMUP):
        model.predict(images[i % len(images)], **predict_args)

    synchronize = _device_synchronizer(device)
    elapsed_ms = []
    for i in range(BENCH_RUNS):
        synchronize()
        t0 = time.perf_counter()
        model.predict(images[i % len(images)], **predict_args)
        synchronize()
        elapsed_ms.append((time.perf_counter() - t0) * 1000)
    return statistics.median(elapsed_ms), _percentile(elapsed_ms, 0.90)


def _device_synchronizer(device):
    if device != "cpu":
        import torch

        if torch.cuda.is_available():
            return torch.cuda.synchronize
    return lambda: None


def _percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    index = (len(ordered) - 1) * quantile
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def _parse_imgsz(items: list[str] | None) -> list[int] | None:
    if not items:
        return None
    sizes = []
    for item in items:
        for value in item.split(","):
            try:
                size = int(value)
            except ValueError:
                raise argparse.ArgumentTypeError(f"invalid --imgsz value: {value!r}")
            if size <= 0:
                raise argparse.ArgumentTypeError("--imgsz values must be positive")
            sizes.append(size)
    return sizes


def _default_device():
    import torch

    return 0 if torch.cuda.is_available() else "cpu"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Evaluate YOLO mAP, negative-frame ghosts, and inference speed."
    )
    parser.add_argument("model", nargs="*", help="model path(s); defaults to config.YOLO_MODEL_PATH")
    parser.add_argument("--models", nargs="+", metavar="MODEL", help="additional model path(s)")
    parser.add_argument(
        "--imgsz", action="append", metavar="N",
        help="inference size; repeat the flag or use comma-separated values",
    )
    parser.add_argument(
        "--bench", action="store_true",
        help=f"benchmark each size after {BENCH_WARMUP} warmups using {BENCH_RUNS} timed calls",
    )
    parser.add_argument(
        "--device", help="Ultralytics device (for example cpu or 0); defaults to CUDA when available",
    )
    args = parser.parse_args(argv)
    try:
        args.imgsz = _parse_imgsz(args.imgsz)
    except argparse.ArgumentTypeError as exc:
        parser.error(str(exc))
    if args.bench and args.imgsz is None:
        parser.error("--bench requires --imgsz")
    return args


def print_results(results, sized=False, bench=False):
    print()
    print(f"{'model':<42}", end="")
    if sized:
        print(f"{'imgsz':>7}", end="")
    print(f"{'mAP50':>7}{'mAP50-95':>10}", end="")
    if bench:
        print(f"{'med ms/f':>9}{'p90 ms/f':>9}", end="")
    else:
        print(f"{'ms/f':>7}", end="")
    for c in GHOST_CONFS:
        print(f"{'ghost@' + f'{c:.2f}':>12}", end="")
    print(f"{'maxconf':>9}")
    for r in results:
        name = Path(r["model"]).name
        print(f"{name:<42}", end="")
        if sized:
            print(f"{r['imgsz']:>7}", end="")
        print(f"{r['map50']:>7.3f}{r['map5095']:>10.3f}", end="")
        if bench:
            print(f"{r['bench_median_ms']:>9.1f}{r['bench_p90_ms']:>9.1f}", end="")
        else:
            print(f"{r['ms_per_frame']:>7.1f}", end="")
        for c in GHOST_CONFS:
            cnt, frac = r["ghost"][c]
            print(f"{f'{cnt}/{r['neg_frames']} ({frac:.0%})':>12}", end="")
        print(f"{r['ghost_max_conf']:>9.2f}")
    print()
    for r in results:
        if r["ghost_class"][0.50]:
            suffix = f"@{r['imgsz']}" if sized else ""
            print(f"  {Path(r['model']).name}{suffix} ghost@0.50 แยกตาม class: "
                  f"{r['ghost_class'][0.50]}")


def main(argv=None):
    args = parse_args(argv)
    models = args.model + (args.models or [])
    models = models or [config.YOLO_MODEL_PATH]

    # Preserve the original no-new-flags execution, including device=0 and table.
    new_mode = args.imgsz is not None or args.bench or args.models is not None or args.device is not None
    if not new_mode:
        results = [eval_model(model) for model in models]
        print_results(results)
        return

    device = args.device if args.device is not None else _default_device()
    if isinstance(device, str) and device.isdigit():
        device = int(device)
    sizes = args.imgsz or [None]
    results = [
        eval_model(model, imgsz=size, device=device, bench=args.bench)
        for model in models for size in sizes
    ]
    print_results(results, sized=args.imgsz is not None, bench=args.bench)


if __name__ == "__main__":
    main()
