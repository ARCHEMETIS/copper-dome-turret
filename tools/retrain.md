# เทรน YOLO รอบใหม่ (รอบ 3)

รันจากโฟลเดอร์โปรเจค (ใช้ค่าเดียวกับรอบ 2: yolov8n, 640px, 60 epochs, GPU):

```powershell
venv\Scripts\yolo.exe detect train model=yolov8n.pt data=dataset/data.yaml epochs=60 imgsz=640 batch=16 device=0 name=train-3
```

เสร็จแล้ว:

1. ดูผลใน `runs/detect/train-3/` (กราฟ + confusion matrix)
2. วัดกับ test set (ห้ามข้าม — valid ถูกใช้เลือก checkpoint ไปแล้ว):
   ```powershell
   venv\Scripts\yolo.exe detect val model=runs/detect/train-3/weights/best.pt data=dataset/data.yaml split=test
   ```
3. ถ้าดีกว่าเดิม: สำรองโมเดลเก่า แล้วสลับตัวใหม่เข้า
   ```powershell
   Copy-Item models\best.pt models\best_2026-07-10_เทรนรอบ2.pt
   Copy-Item runs\detect\train-3\weights\best.pt models\best.pt
   ```
4. ลองของจริง: `venv\Scripts\python.exe tools\test_on_webcam.py` — เอาเสื้อขาว/เทามาโบกหน้ากล้องดูว่าผีหายไหม
5. ผีหายแล้ว → ลด `YOLO_CONF` ใน `src/config.py` กลับ (0.65 → 0.5)
6. ⚠ ranging: กรอบโมเดลใหม่อาจต่างจากเดิม → เก็บข้อมูลซ้ำด้วย
   `tools/collect_ranging_data.py` แล้ว fit ใหม่ **ทั้งสองอย่าง**:
   `real_size_mm` และ `ASPECT_CORRECTION` (รัน `tools/fit_aspect.py`
   แล้ววาง block ที่มันพิมพ์ลง `src/config.py`)
   — แถวเก่าใน ranging_log.csv ไม่ต้องลบ: ทุกแถวแท็กด้วยชื่อ+hash ของโมเดล
   (`config.yolo_model_tag()`) เครื่องมือทุกตัวกรองเฉพาะแถวของโมเดลปัจจุบันเอง

## อยากแม่นขึ้นอีก (ถ้ามีเวลา)

- `model=yolov8s.pt` — ตัวใหญ่ขึ้น แม่นขึ้นชัดเจน ยัง realtime สบายบน GPU
  (แลกกับช้าลงนิดหน่อยตอน inference)
- `imgsz=960` — ช่วยเป้าตัวเล็ก/ไกล (แลกกับเทรนช้าขึ้น ~2 เท่า)
- negative เพิ่มเรื่อยๆ ได้ ไม่มีโทษ ตราบใดที่ไม่มีตุ๊กตาหลุดเข้าไปในรูป
