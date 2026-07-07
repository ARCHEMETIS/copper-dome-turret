# 🎯 Copper Dome — Vision-Guided Auto-Aiming Turret

> ป้อมปืนอัตโนมัติเล็งเป้าด้วยกล้อง ยิงลูกบอลไม้ใส่เป้าที่ระยะไม่คงที่ — ควบคุมด้วย **Python ทั้งระบบ** (ไม่มีโค้ด C บน Arduino แม้แต่บรรทัดเดียว)
>
> ARIS Project III — Mini-project 1 | กำหนดแข่ง: 30 ก.ค. 2026

![Python](https://img.shields.io/badge/Python-3.12-blue) ![OpenCV](https://img.shields.io/badge/OpenCV-5.0-green) ![YOLOv8](https://img.shields.io/badge/YOLO-v8n-orange) ![Arduino](https://img.shields.io/badge/Arduino-Uno%20R3%20(StandardFirmata)-teal)

---

## 📌 โจทย์

สร้างป้อมยิงที่:
- ตรวจจับตุ๊กตา 3 ตัว (ไดโนเสาร์เขียว, คาปิบาร่า, ช้างเทา) ผ่านกล้อง
- ผู้ใช้เลือกเป้าผ่าน UI → ป้อมหันหาเป้าเอง → ยิงลูกบอลไม้ให้โดน
- **ตำแหน่งเป้าไม่คงที่** — ห้าม hardcode พิกัด ระบบต้องวัดระยะและปรับแรงยิงเองทุกนัด
- เกณฑ์วัดผล: ยิงถูกตัวที่เลือก **5 จาก 10 นัด** ที่ระยะ ~1.5 m (เป้าอยู่สูงกว่าแท่นปืน 400 mm)
- ข้อจำกัด: ใช้ Python เท่านั้น, ห้ามซื้ออุปกรณ์เพิ่ม (ใช้มือถือแทน webcam)

## 💡 แนวคิดการแก้โจทย์ "เป้าอยู่ตรงไหนก็ได้"

ระบบไม่พยายามรู้พิกัดโลกจริงของเป้าเลย แต่ใช้ 3 เทคนิคร่วมกัน:

1. **Visual Servoing** — ติดกล้อง (มือถือ) บนป้อมให้หมุนไปด้วยกัน แล้วควบคุมแบบ closed-loop:
   หมุน → หยุด → เช็คภาพ → หมุนแก้ ทำซ้ำจนเป้าอยู่กลางเฟรม (error < deadband)
   ข้อดี: ไม่ต้อง calibrate ตำแหน่งกล้องเทียบลำกล้อง ไม่ต้องแปลงพิกัด

2. **Monocular Ranging** — วัดระยะด้วยกล้องตัวเดียวจากขนาดวัตถุ:
   `ระยะ = focal_px × ขนาดจริง(mm) ÷ ขนาดในภาพ(px)`
   โดย calibrate `focal_px` ครั้งเดียวหลังล็อก focus มือถือ

3. **Ballistics จากตาราง calibration** — ล็อกมุมเงยตายตัว เหลือตัวแปรเดียวคือความเร็วล้อ flywheel (PWM duty)
   ยิงจริงหลายระยะ → เก็บตาราง `duty ↔ ระยะตก` → interpolate ขณะแข่ง
   (สูตร projectile motion ใช้ประกอบการนำเสนอ แต่ความแม่นจริงมาจากข้อมูลยิงจริง)

```
เลือกเป้าใน UI ─► visual servoing หมุนป้อมจนเป้ากลางภาพ ─► วัดระยะจากขนาดในภาพ
        ─► interpolate ตารางเป็น PWM duty ─► ปั่น flywheel ~1.2s ─► servo ดันลูก ─► 🎯
```

## 🏗️ สถาปัตยกรรมระบบ

```
                         PC (Python ทั้งหมด)
   ┌──────────────────────────────────────────────────────┐
   │  main.py (tkinter UI: วิดีโอสด + เลือกเป้า + FIRE)      │
   │     ├─ detector.py   HSV / YOLOv8n (สลับได้ใน config)  │
   │     ├─ aiming.py     visual servoing loop              │
   │     ├─ ranging.py    ระยะจากขนาด + duty จากตาราง       │
   │     └─ hardware.py   ── pyfirmata2 ──► USB serial      │
   └──────────────────────────────────────────┬───────────┘
                                              │
        มือถือ (Camo/USB) = webcam             ▼
                              Arduino Uno R3 + StandardFirmata
                              (ทำหน้าที่เป็นแค่ I/O — ไม่มี logic)
                                 │ PWM D5,D6 ──► L298N ──► DC motor ×2 (flywheel)
                                 │ D9  ──► MG945 #1 (pan หมุนป้อม)
                                 │ D10 ──► MG945 #2 (feeder ดันลูก)
```

**ทำไมไม่เขียน C?** ใช้เฟิร์มแวร์สำเร็จรูป StandardFirmata แล้วสั่งขา I/O สดๆ จาก Python ผ่าน `pyfirmata2` — logic ทุกบรรทัดอยู่ฝั่ง PC ตรงตามกติกา "Python only" และ debug ง่ายกว่ามาก

## 🔩 Bill of Materials

### อิเล็กทรอนิกส์ (ชุดที่ได้รับแจก)

| อุปกรณ์ | หน้าที่ในระบบ |
|---|---|
| Arduino Uno R3 + Sensor Shield v5 | I/O ผ่าน StandardFirmata (ถอด jumper servo power บน shield) |
| DC Motor 3–6V ×2 + L298N driver | ล้อยิงคู่ (flywheel) — PWM duty คุมความเร็ว = คุมระยะยิง |
| Servo MG945 ×2 (torque ~10 kg·cm) | #1 pan หมุนป้อม / #2 feeder ป้อนลูกทีละลูก |
| Li-ion 18650 ×2 (อนุกรม 7.4V) | จ่าย L298N ตรง + ผ่าน buck ไปเลี้ยง servo |
| DC-DC Buck converter | ลดเหลือ 6V เลี้ยง servo (ห้ามดึงจาก 5V USB — บอร์ดจะรีเซ็ต) |
| Diode ×2 + Capacitor 100µF ×2 | กัน noise / ไฟกระชากจากมอเตอร์ |
| มือถือ + Camo | webcam ความละเอียดสูง มี manual focus/exposure lock |

**จุดวิศวกรรมที่ต้องระวัง:** กราวด์ทุกส่วน (แบต, buck, L298N, Uno) ต้องต่อร่วมกัน ไม่งั้นสัญญาณ PWM/servo เพี้ยน

### 🖨️ ชิ้นส่วน 3D Print

| ชิ้นส่วน | โมเดลต้นทาง | การดัดแปลง |
|---|---|---|
| **ตัวยิง flywheel + feeder + แมกกาซีน** | [HIGH-SPEED Ping-Pong Ball Shooter XRP](https://www.printables.com/model/951454-high-speed-ping-pong-ball-shooter-xrp) (Printables #951454) | สเกลช่องยิงตาม Ø ลูกบอลไม้จริง — ลูกไม้**แข็งไม่ยุบ**ต่างจากปิงปอง ระยะห่างล้อต้อง = Ø ลูก − 1–2 mm ให้ยางหุ้มล้อเป็นตัวยุบแทน, ล้อพิมพ์ infill 50%+ เพิ่มมวลกันรอบตก, เช็ครูเพลามอเตอร์ (2 vs 2.3 mm) |
| **ฐาน Pan-Tilt** | [Pan-Tilt for MG995/MG996/DS3218](https://www.thingiverse.com/thing:3458238) (สกรู M3×10) | MG945 ใช้เคสเดียวกับ MG995/996 จึง mount ร่วมกันได้ — ใช้เฉพาะแกน pan, มุมเงยล็อกตายตัว **~30–35°** (จากการวิเคราะห์ projectile: ที่มุม ≤25° ความสัมพันธ์ความเร็ว↔ระยะไม่ monotonic เพราะเป้าสูงกว่าปากกระบอก — ดู `tools/ballistics_calc.py`), เสริม bearing/แหวนรองถ้าแท่นโยก |
| **ที่จับมือถือ** | [Phone holder with bracket](https://www.printables.com/model/472468) (Printables #472468) | ยึดบนส่วนหมุนของป้อม ให้แกนเลนส์ขนานลำกล้อง — กล้องหมุนตามป้อม (หัวใจของ visual servoing) |

*เครดิตโมเดลทั้งหมดเป็นของผู้ออกแบบต้นทางตามลิขสิทธิ์ที่ระบุในแต่ละหน้าโมเดล — ใช้เพื่อการศึกษา*

### โครงสร้างเชิงกล (บนลงล่าง)

1. ส่วนหมุน: มือถือ+bracket / ตัวยิง XRP (มุมเงยคงที่) / แมกกาซีน gravity-feed + feeder servo
2. แท่นหมุนเสียบ servo horn + สกรูล็อกกลาง
3. Pan servo MG945 ใน bracket ยึดฐาน
4. ฐาน 400×400 mm (นิ่ง) — วางอิเล็กทรอนิกส์ทั้งหมด + ถ่วงน้ำหนักกัน recoil, เดินสายขึ้นส่วนหมุนแบบหย่อนรองรับ ±40°

## ⚡ วงจร

```
18650 ×2 (7.4V) ──┬──► L298N ──► DC motor ×2 (flywheel, หมุนสวนทางกัน)
                  └──► Buck (6V) ──► Servo rail ของ Sensor Shield (ถอด jumper!)
PC ──USB──► Arduino Uno (StandardFirmata)
            D5/D6 (PWM) ──► ENA/ENB    D2,D4,D7,D8 ──► IN1-4    D9/D10 ──► Servo signal
⚠ Common ground ทุกส่วน
```

## 📂 โครงสร้างโค้ด

```
src/                        โปรแกรมหลัก
├── config.py               ค่าคงที่/calibration ทั้งหมดรวมที่เดียว (single source of truth)
├── hardware.py             คลาส Turret — abstraction เดียวที่แตะ pyfirmata2
├── camera.py               เปิดกล้อง (auto-detect index)
├── detector.py             ตรวจจับเป้า: HsvDetector / YoloDetector (interface เดียวกัน)
├── ranging.py              ระยะจากขนาดในภาพ + แปลงระยะ→duty (np.interp)
├── aiming.py               visual servoing loop (P-control + deadband + confirm frames)
└── main.py                 tkinter UI (วิดีโอสด, เลือกเป้า, ยิงใน thread แยก)

tools/                      สคริปต์สนับสนุน
├── test_hardware.py        ทดสอบ servo/ล้อ/feeder ด้วยคีย์บอร์ด (รันก่อนทุกไฟล์)
├── calibrate_focal.py      หา focal length ของกล้อง (ROI selection)
├── calibrate_pwm.py        เก็บตาราง duty↔ระยะจากการยิงจริง
├── capture_dataset.py      ถ่ายภาพ dataset สำหรับเทรน YOLO
├── ballistics_calc.py      ตารางคำนวณ projectile (ใช้เลือกมุมเงย + ประกอบสไลด์)
└── smoke_test.py           ทดสอบทั้ง loop อัตโนมัติบน simulator (regression test)

learn/                      บทเรียน computer vision (รันได้โดยไม่มีฮาร์ดแวร์)
├── notebooks/               Jupyter notebooks 6 บท (00-05) อธิบายทุกบรรทัด + แบบฝึกหัด — ทางหลักสำหรับเรียน
└── 01_camera.py … 05_yolo_demo.py   เวอร์ชันสคริปต์สด (วิดีโอต่อเนื่อง, แถบเลื่อนลากได้เต็มจอ)
```

เอกสารประกอบ (ภาษาไทย): [`docs/แผนโปรเจค-CopperDome.md`](docs/แผนโปรเจค-CopperDome.md) (แผนงาน+วิเคราะห์ความเสี่ยง), [`docs/คู่มือโค้ด-อ่านก่อน.md`](docs/คู่มือโค้ด-อ่านก่อน.md) (setup + troubleshooting) และ [`docs/ROADMAP.md`](docs/ROADMAP.md) (แผนที่การเรียนรู้ vision/robotics อ้างอิงคอร์ส/หนังสือมาตรฐาน)

**เพิ่งเริ่มจากศูนย์?** อ่าน [`START-HERE.md`](START-HERE.md) ก่อนไฟล์อื่นทั้งหมด

## 🚀 Getting Started

```powershell
# 1) อัปโหลดเฟิร์มแวร์ (ครั้งเดียว): Arduino IDE → File > Examples > Firmata > StandardFirmata
# 2) ติดตั้ง
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
# 3) ทดสอบฮาร์ดแวร์
venv\Scripts\python.exe tools\test_hardware.py
# 4) รันระบบเต็ม
venv\Scripts\python.exe src\main.py
```

**ยังไม่มีฮาร์ดแวร์?** รันโหมดจำลองได้ทั้งระบบ — ป้อมเสมือน + สนามเสมือนที่สุ่มตำแหน่งเป้าใหม่ทุกนัด ใช้โค้ด vision/aiming/ranging ตัวจริงทั้งหมด:

```powershell
venv\Scripts\python.exe src\main.py --sim        # UI เต็ม เลือกเป้า กดยิง ดูสถิติโดน/พลาด
venv\Scripts\python.exe tools\smoke_test.py      # ทดสอบอัตโนมัติ 9 นัด (ต้องผ่านก่อน commit)
```

## 🧠 Vision: สองโหมดสลับได้

| | HSV segmentation | YOLOv8n (fine-tuned) |
|---|---|---|
| ข้อดี | ใช้ได้ทันที ไม่ต้องเทรน, เร็วมาก | แยกวัตถุสีจืด (คาปิบาร่า/ช้างเทา) ได้, ทนแสงเปลี่ยน |
| ข้อเสีย | แยกได้ดีเฉพาะสีสด (ไดโนเขียว) | ต้องเก็บภาพ ~100–150 รูป/ตัว + เทรน |
| บทบาท | fallback + ใช้พัฒนาระบบช่วงแรก | โหมดหลักวันแข่ง |

สลับด้วยตัวแปรเดียว: `DETECTOR = "hsv" | "yolo"` ใน `config.py` — ทั้งคู่ implement interface `detect(frame, target) -> Detection` เหมือนกัน

## 📊 สถานะโปรเจค

- [x] ออกแบบระบบ + วิเคราะห์ความเสี่ยง
- [x] โครงสร้างโค้ดครบทุกโมดูล (vision / aiming / ranging / hardware / UI / calibration tools)
- [x] ชุดบทเรียน vision สำหรับฝึกก่อนได้อุปกรณ์
- [x] Simulator + smoke test: พิสูจน์ loop เล็ง→วัดระยะ→ยิง ครบวงจร (9/9 ใน sim)
- [x] วิเคราะห์ ballistics → เลือกมุมเงย 30–35° (หลีกเลี่ยงช่วง non-monotonic)
- [ ] ประกอบฮาร์ดแวร์ + พิมพ์ชิ้นส่วน 3D
- [ ] Calibrate: focal length, ตาราง PWM↔ระยะ, จูน servo
- [ ] เก็บ dataset + เทรน YOLOv8n
- [ ] ทดสอบรวมระบบ + เก็บสถิติความแม่น (เป้า >5/10 แบบมี margin)
- [ ] นำเสนอ 30 ก.ค. 2026

## 👤 Author

**ARCHEMETIS** — ARIS Project III (2026)
