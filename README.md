# 🎸 MeloTab

โปรแกรม Desktop (รัน local ทั้งหมด) สำหรับมือกีตาร์สายเมโลดี้
**วางลิงก์ YouTube หรือไฟล์เสียง → แกะเมโลดี้เสียงร้อง → Piano Roll → Guitar Tab → Export เป็นรูปรายท่อน**

หลักการ: **ความแม่นยำของโน้ตมาก่อนความเร็ว** และ **คนตรวจ/แก้ได้ง่ายที่สุด** (Human-in-the-loop)

## สถานะปัจจุบัน

> 🚧 **Phase 2 จบแล้ว — ใช้งานได้ในเบราว์เซอร์ (dev mode): นำเข้าไฟล์เสียง → วิเคราะห์ → ตรวจ/แก้โน้ตบน Piano Roll → เล่นฟังเทียบ** ยังไม่ใช่แอป desktop (Tauri อยู่ Phase 6) และยังไม่มี Guitar Tab

| Phase | เนื้อหา | สถานะ |
|---|---|---|
| 0 | Setup & Spike (ทดสอบโมเดลทีละตัว วัด VRAM/เวลา) | ✅ จบ (เหลือ 2 ข้อยกไป Phase 1 ดูด้านล่าง) |
| 1 | MVP หลังบ้าน + Piano Roll พื้นฐาน | ✅ จบ (เหลือ SQLite index/autosave/history ย้ายไปทำพร้อมการแก้โน้ต) |
| 2 | ความแม่นยำของโน้ต + แก้โน้ต | ✅ จบ (ยังไม่ได้วัด Note F1 กับ ground truth จริง) |
| 3 | Tab Engine + Editor | ⏳ ถัดไป |
| 4 | ทฤษฎีดนตรีครบ + Chord Sheet + Metronome | ⏳ |
| 5 | เทคนิคกีตาร์ + Export | ⏳ |
| 6 | ขัดเกลา & ฟีเจอร์เสริม | ⏳ |

ตอนนี้มีเอกสารออกแบบ ([`plan.md`](plan.md)) และผลทดลอง Phase 0 บนเพลงจริง 2 เพลง (49 วินาทีและ 4:50)

### ผล Phase 0 โดยสรุป
- ทดลองแล้วใช้ได้: แยกเสียงร้อง (Mel-Band RoFormer), karaoke (ตัดเสียงประสาน), de-reverb, f0 (RMVPE, torchcrepe), แบ่งโน้ต (SOME), beat/downbeat (Beat This!), คอร์ด (BTC)
- เพลง 4:50 ใช้ GPU ≈ 1 นาที (ไม่รวม karaoke + de-reverb ≈ +3 นาที) และ VRAM ต่อโมเดลต่ำกว่า 5 GB ตารางเต็มอยู่ใน `plan.md` หัวข้อ 18
- ข้อค้นพบสำคัญ: เสียงประสานใน vocal stem ทำให้ SOME ให้โน้ตผิด octave ได้ — ใช้ karaoke model ช่วยได้มาก; Beat This! อาจสลับ tempo ครึ่ง/เท่าตัว ต้องมี tempo normalization; BTC ให้คอร์ดสั่น ต้องทำ smoothing
- ที่ยังไม่ได้ทำ/ยกไป Phase 1: สคริปต์เดียวจากลิงก์ YouTube → MIDI (ดาวน์โหลดจาก YouTube ติด HTTP 403 ในเครื่องนี้ ตอนนี้ใช้ไฟล์เสียงที่โหลดมาเอง), ROSVOT / essentia / allin1 ยังไม่ได้ลองหรือลงไม่สำเร็จบน Windows
- ความแม่นยำของโน้ตตรวจด้วยการฟังเทียบบนเพลงเพียง 2 เพลง ยังไม่มี ground truth

## ฟีเจอร์ที่วางแผนไว้
- Ingest จาก YouTube / ไฟล์เสียง, แยกเสียงร้องนำ (lead vocal)
- วิเคราะห์ Key, Tuning, BPM/Tempo map, Time signature, ท่อนเพลง, คอร์ด
- แกะโน้ตเสียงร้อง (พร้อม octave, cents, confidence) แสดงเป็น Piano Roll
- Chord Sheet + เนื้อร้อง + Metronome ตามจังหวะเพลงจริง
- Auto Guitar Tab (Viterbi) + Block Mode + แปลงลูกคอเป็นเทคนิคกีตาร์
- แนะนำคีย์ที่เล่นง่าย + Capo, Tab Editor จิ้มแก้ได้ทุกตัว
- Export รายท่อนเป็นรูป (PNG/SVG/PDF) และ MIDI / MusicXML / Guitar Pro

## Tech Stack (ตามแผน)
- **Frontend**: React + TypeScript + Vite, Tauri 2, PixiJS, Web Audio
- **Backend**: Python 3.11, FastAPI, PyTorch (CUDA), Numba
- **เครื่องเป้าหมาย**: i5-13500HX, RTX 4060 Laptop 8 GB, RAM 32 GB, Windows 11

## การติดตั้งและรัน (dev)
ทดสอบแล้วบน Windows 11 + RTX 4060 (driver ใหม่ รองรับ CUDA 13) ขั้นตอนทั้งหมดยังเป็นแบบ manual:

1. ติดตั้ง Python 3.11, Node.js, ffmpeg (ต้องอยู่ใน PATH)
2. Backend:
   ```powershell
   cd backend
   py -3.11 -m venv .venv
   .venv\Scripts\python -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu130
   .venv\Scripts\python -m pip install -r requirements.txt
   ```
3. ดึงโค้ด/น้ำหนักโมเดลที่ไม่มีบน PyPI (SOME, RMVPE, BTC) ตามคำอธิบายใน `backend/requirements.txt` (วางใน `third_party/` และ `models/`)
4. รัน backend: `cd backend && .venv\Scripts\python -m uvicorn melotab.api.app:app --port 8000`
5. รัน frontend: `cd apps/web && npm install && npm run dev` แล้วเปิด http://localhost:5173
6. ลากไฟล์เสียงเข้าหน้าเว็บ (การดาวน์โหลดจากลิงก์ YouTube ยังไม่รองรับในแอป — yt-dlp ติด HTTP 403 บนเครื่องที่ทดสอบ)

CLI (ไม่ต้องเปิดเว็บ): `cd backend && .venv\Scripts\python -m melotab.cli analyze เพลง.mp3 --out ผลลัพธ์ [--karaoke] [--dereverb]`

เทสต์: `cd backend && .venv\Scripts\python -m pytest tests` · `cd apps/web && npm test` · ทดสอบ UI จริงด้วย Chrome: เปิด backend + dev server แล้ว `npm run e2e`

### ใช้งานได้แล้วใน Phase 1
- วิเคราะห์ไฟล์เสียง → เมโลดี้เสียงร้อง (แยกเสียง → f0 → โน้ต), คีย์, BPM/beat/downbeat (เร็ว ~50 วินาทีต่อเพลง 4:50 บน GPU ที่ทดสอบ; ตัวเลือก karaoke/de-reverb ช้าลง +~3 นาที แต่แม่นขึ้นเมื่อมีเสียงประสาน)
- Piano Roll: ชื่อโน้ต+octave, ไฮไลต์คีย์, เส้น pitch จริง, โน้ตความมั่นใจต่ำมีขอบส้ม, คลิกโน้ต/คีย์เพื่อฟัง
- เล่นเพลงพร้อม synth ของโน้ต (ฟังเทียบซ้าย/ขวา) และ metronome ตาม beat grid จริง
- Status bar: ความคืบหน้ารายขั้น, GPU/VRAM/CPU/RAM, ยกเลิกงาน; cache ต่อขั้น (เพลงเดิมเปิดซ้ำทันที)

### เพิ่มใน Phase 2
- แก้โน้ตบน Piano Roll: ลากขึ้นลง/ลากขอบ/ดับเบิลคลิกเพิ่ม, ↑↓ Delete S(แบ่ง) M(รวม) Ctrl+Z/Y, snap ตาม beat grid
- autosave + เวอร์ชันก่อนหน้า (กู้คืนได้), แผง "ความละเอียดโน้ต" (แกะใหม่โดยไม่รันโมเดลซ้ำ)
- ธงโน้ตที่ควรตรวจ + ปุ่ม N กระโดดไปโน้ตถัดไป, แก้ octave อัตโนมัติตาม f0 (ติดธงให้ตรวจ), ประเมิน tuning offset
- สคริปต์ประเมินด้วย mir_eval: `python -m melotab.evaluate --ref แกะมือ.mid --est Projects/<id>/song.json`

### ข้อจำกัดที่รู้ (Phase 1–2)
- ยังไม่มี Guitar Tab/คอร์ด/เนื้อร้อง/export
- ความถูกต้องของโน้ตตรวจด้วยการฟังเทียบบน 2 เพลงเท่านั้น ยังไม่มี ground truth
- เปอร์เซ็นต์ความคืบหน้าเป็นรายขั้น (ไม่มี % ภายในขั้นแยกเสียง), ยกเลิกได้ระหว่างขั้นเท่านั้น
- เสียงที่ออกจากลำโพงจริงยังไม่ได้ตรวจโดยเครื่องมืออัตโนมัติ

สิ่งที่รู้แล้วว่าจะต้องใช้ (ดู [`backend/requirements.txt`](backend/requirements.txt)):
1. Python 3.11, ffmpeg (อยู่ใน PATH), NVIDIA driver + CUDA 12.x
2. ติดตั้ง PyTorch ให้ตรงกับ CUDA ก่อน แล้วค่อย `pip install -r backend/requirements.txt`
3. บางโมเดล (RMVPE, SOME, BTC ฯลฯ) ต้องติดตั้งเองจาก repo — รายละเอียดอยู่ในไฟล์ requirements

## โครงสร้างโปรเจกต์
โครงสร้างเป้าหมายอยู่ใน `plan.md` หัวข้อ 21 ปัจจุบันมีจริงเฉพาะ:

```
plan.md              แผนออกแบบฉบับเต็ม
CLAUDE.md            กฎและคำแนะนำสำหรับ Claude Code
.claude/             บันทึกความคืบหน้า (PROGRESS, DECISIONS, logs)
backend/melotab/     FastAPI + pipeline (separation, f0, notes, rhythm, key) + job queue + cache
backend/scripts/     สคริปต์ทดลองของ Phase 0
backend/tests/       pytest
apps/web/            React + Vite + PixiJS (Piano Roll)
third_party/ models/ โค้ดและน้ำหนักโมเดลภายนอก (ไม่เข้า git)
```

## ข้อควรระวัง
- ใช้เพื่อการเรียน/ส่วนตัว — ตรวจลิขสิทธิ์เพลงและเงื่อนไข YouTube ก่อนเผยแพร่แทป
- บางโมเดลเป็น non-commercial ต้องตรวจ license ก่อนแจกจ่าย/ขาย
