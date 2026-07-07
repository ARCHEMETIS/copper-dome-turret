# Learning Roadmap — Copper Dome

> แผนที่การเรียนรู้ฝั่ง vision/robotics ของโปรเจคนี้ **ไม่ใช่การก็อป syllabus ของที่ไหน** —
> เป็นการรวมลำดับหัวข้อจากคอร์ส/หนังสือที่มีชื่อเสียงและฟรี มาปรับให้ตรงกับที่โปรเจคนี้ต้องใช้จริง
> ทุกแหล่งอ้างอิงให้เครดิตไว้ชัดเจน ไม่คัดลอกเนื้อหามาแปะ

**วิธีอ่านตาราง:** ✅ = มีบทเรียนของ repo นี้เองแล้ว (`learn/notebooks/`) | 📝 = ยังไม่มีบทเรียนในนี้ ใช้แหล่งอ้างอิงภายนอกไปก่อน

---

## Phase 0 — พื้นฐาน (Foundations)

| หัวข้อ | สถานะ | อ้างอิงเชิงลึก |
|---|---|---|
| Python, numpy array, indexing | ✅ `learn/notebooks/00_python_numpy_basics.ipynb` | — |
| Linear algebra ที่ใช้ใน CV/ML (เวกเตอร์, matrix, dot product) | 📝 | **3Blue1Brown — "Essence of Linear Algebra"** (ค้นหาใน YouTube channel 3Blue1Brown) วิดีโอสั้น เห็นภาพ ไม่ต้องมีพื้นฐานมาก่อน |
| Calculus พื้นฐาน (derivative, gradient) — ใช้ตอนเข้าใจ backprop | 📝 | 3Blue1Brown — "Essence of Calculus" (ซีรีส์เดียวกัน, channel เดียวกัน) |

## Phase 1 — Classical Computer Vision

| หัวข้อ | สถานะ | อ้างอิงเชิงลึก |
|---|---|---|
| ภาพดิจิทัล, BGR/RGB, กล้อง | ✅ `01_camera_and_images.ipynb` | — |
| Color spaces (HSV), masking, morphology | ✅ `02_color_and_hsv.ipynb` | OpenCV official docs — tutorial "Changing Colorspaces" + "Morphological Transformations" (opencv.org) |
| Contours, blob detection, visual servoing เบื้องต้น | ✅ `03_tracking_and_aiming.ipynb` | — |
| Monocular distance estimation (สามเหลี่ยมคล้าย) | ✅ `04_distance_measurement.ipynb` | — |
| ภาพรวมเชิงลึกกว่านี้ (filters, edge detection, feature matching) | 📝 | **cs231n.stanford.edu** (Stanford CS231n) — lecture ต้นๆ ก่อนเข้าเรื่อง neural net เป็น classical CV ล้วนๆ |

## Phase 2 — Deep Learning / Object Detection

| หัวข้อ | สถานะ | อ้างอิงเชิงลึก |
|---|---|---|
| YOLO เบื้องต้น (predict, confidence, ทำไมต้องเทรนเอง) | ✅ `05_yolo_intro.ipynb` | — |
| CNN คืออะไร, ทำงานยังไง (theory) | 📝 | **cs231n.stanford.edu** — คอร์ส CV/deep learning มาตรฐานที่สุด สไลด์+notes ฟรีทั้งหมด |
| ลงมือเทรนโมเดลเองแบบ project-based (ไม่เน้นทฤษฎีก่อน) | 📝 | **fast.ai** — "Practical Deep Learning for Coders" (course.fast.ai) เน้นลงมือทำเร็ว เหมาะถ้าอยากได้ momentum |
| เทรน YOLO fine-tune จากรูปตุ๊กตาจริง | 📝 (แผนงานอยู่ใน `docs/คู่มือโค้ด-อ่านก่อน.md`) | Ultralytics official docs (docs.ultralytics.com) |

## Phase 3 — Robotics & Control

| หัวข้อ | สถานะ | อ้างอิงเชิงลึก |
|---|---|---|
| P-controller ง่ายๆ, deadband, visual servoing loop | ✅ `03_tracking_and_aiming.ipynb` + `src/aiming.py` | — |
| Control theory จริงจัง (PID, state-space, kinematics) | 📝 | **Modern Robotics** โดย Kevin Lynch (Northwestern) — ฟรีบน Coursera ในชื่อ "Modern Robotics Specialization" มี textbook PDF ฟรี + โค้ดตัวอย่างบน GitHub ของผู้เขียน |
| Projectile motion / ballistics | ✅ `tools/ballistics_calc.py` | — |

## Phase 4 — Embedded / Hardware Integration

| หัวข้อ | สถานะ | อ้างอิงเชิงลึก |
|---|---|---|
| Arduino + StandardFirmata + pyFirmata2 | ✅ `docs/คู่มือโค้ด-อ่านก่อน.md`, `src/hardware.py` | Arduino official docs (docs.arduino.cc) |
| Servo/motor driver พื้นฐาน (L298N, PWM) | ✅ แผนวงจรใน `docs/แผนโปรเจค-CopperDome.md` | — |
| วงจรไฟฟ้าเชิงลึกกว่านี้ (ถ้าอยากต่อยอด) | 📝 | ทั่วไป: ค้นหา "Arduino motor driver tutorial" บนเว็บ Arduino official หรือ SparkFun |

---

## หลักการใช้ roadmap นี้

1. **อ่านจากบนลงล่าง** ทำ Phase 0-1 ให้จบก่อน (มีบทเรียนในนี้ครบแล้ว) ค่อยไป Phase 2-4
2. แถวที่มี ✅ = ลงมือทำได้เลยตอนนี้ในนี้ ไม่ต้องหาที่อื่น
3. แถวที่มี 📝 = repo นี้ยังไม่มีบทเรียนของตัวเอง ให้ไปดูจากแหล่งอ้างอิงที่ให้ไว้โดยตรง — **ไปเรียนจากต้นทาง อย่าลอกเนื้อหาเขามาแปะในนี้**
4. ถ้าจะเพิ่มบทเรียนใหม่ในอนาคต ให้เขียนคำอธิบาย/ตัวอย่างเป็นของตัวเอง (เหมือน `learn/notebooks/`) แล้วอ้างอิงว่าลำดับหัวข้อ/แนวคิดมาจากที่ไหน ไม่ใช่คัดลอกสไลด์หรือข้อความมา

## เครดิตแหล่งอ้างอิง

- **CS231n: Convolutional Neural Networks for Visual Recognition** — Stanford University
- **Practical Deep Learning for Coders** — fast.ai (Jeremy Howard et al.)
- **Essence of Linear Algebra / Essence of Calculus** — 3Blue1Brown (Grant Sanderson)
- **Modern Robotics: Mechanics, Planning, and Control** — Kevin M. Lynch & Frank C. Park, Northwestern University
- **OpenCV** และ **Ultralytics YOLO** — เอกสารทางการของแต่ละไลบรารี
- **Arduino** — เอกสารทางการของ Arduino
