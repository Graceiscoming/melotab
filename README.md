# 🎸 MeloTab

โปรแกรม Desktop (รัน local ทั้งหมด) สำหรับมือกีตาร์สายเมโลดี้
**วางลิงก์ YouTube หรือไฟล์เสียง → แกะเมโลดี้เสียงร้อง → Piano Roll → Guitar Tab → Export เป็นรูปรายท่อน**

หลักการ: **ความแม่นยำของโน้ตมาก่อนความเร็ว** และ **คนตรวจ/แก้ได้ง่ายที่สุด** (Human-in-the-loop)

## สถานะปัจจุบัน

> 🚧 **Phase 6 (ส่วนที่ทำแล้ว ดูตาราง) — ใช้งานได้ในเบราว์เซอร์หรือเป็นแอป desktop (Tauri, dev-packaged): นำเข้า → วิเคราะห์ → แก้โน้ต → Guitar Tab + เทคนิค → Chord Sheet → ซ้อม (คอกีตาร์วิ่ง + ฟังจากไมค์) → Export (รูป/วิดีโอ/MIDI/MusicXML/GP5/…)**

| Phase | เนื้อหา | สถานะ |
|---|---|---|
| 0 | Setup & Spike (ทดสอบโมเดลทีละตัว วัด VRAM/เวลา) | ✅ จบ (เหลือ 2 ข้อยกไป Phase 1 ดูด้านล่าง) |
| 1 | MVP หลังบ้าน + Piano Roll พื้นฐาน | ✅ จบ (เหลือ SQLite index/autosave/history ย้ายไปทำพร้อมการแก้โน้ต) |
| 2 | ความแม่นยำของโน้ต + แก้โน้ต | ✅ จบ (ยังไม่ได้วัด Note F1 กับ ground truth จริง) |
| 3 | Tab Engine + Editor | ✅ จบ (ความยาก/น้ำหนักยังไม่ปรับกับนักกีตาร์จริง) |
| 4 | ทฤษฎีดนตรีครบ + Chord Sheet + Metronome | ✅ จบ (คอร์ด/ท่อน/เนื้อยังไม่วัดกับ ground truth; ไม่มี allin1/WhisperX) |
| 5 | เทคนิคกีตาร์ + Export | ✅ จบ (เกณฑ์ ornament/GP ยังไม่ได้ทดสอบกับเพลงที่แกะมือ/โปรแกรม Guitar Pro จริง) |
| 6 | ขัดเกลา & ฟีเจอร์เสริม | 🟡 ทำบางส่วน: Tauri shell, Model Manager, Batch, Harmony, Fretboard animation, Practice Mode, Video export — ยังไม่ทำ: TensorRT/ONNX, ตัวติดตั้งที่รวม Python/โมเดล |

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

เทสต์: `cd backend && .venv\Scripts\python -m pytest tests` · `cd apps/web && npm test` · ทดสอบ UI จริงด้วย Chrome (ต้องเปิด backend + dev server ก่อน): `npm run e2e` · `e2e:edit` · `e2e:sens` · `e2e:tab`

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

### เพิ่มใน Phase 3
- **Guitar Tab อัตโนมัติ**: เลือกตำแหน่ง (สาย, ช่อง) ที่เล่นง่ายสุดแต่ pitch ถูกต้องเสมอ (Viterbi + โมเดลตำแหน่งมือ) — โน้ตหนึ่งตัวใช้เวลาไม่ถึง 1 ms ต่อโน้ต
- ตั้งค่า: ยกคีย์ (transpose), capo, จูนนิ่ง (Standard/Eb/Drop D/DADGAD), สไตล์ (สมดุล/เหมือนเสียงร้อง/ง่ายสุด/สว่าง/หนา)
- **Block Mode**: จำกัดโซนบนคอ (ตำแหน่งตามสเกล 7 ตำแหน่ง / Pentatonic box / Custom) พร้อม fretboard และ % โน้ตที่อยู่ใน block
- **แนะนำคีย์ + Capo**: ลองทุกคีย์/capo แยก "เสียงเท่าต้นฉบับ" กับ "เปลี่ยนคีย์"
- Playability: ไฮไลต์จุดที่เปลี่ยนตำแหน่งไม่ทัน/ต้องยืดนิ้ว, heatmap ความยาก, คะแนน 1–10 (ประมาณการ)
- **Tab Editor**: คลิก/พิมพ์เลขช่อง/ย้ายสายรักษา pitch/ตำแหน่งทางเลือก Top-3/ล็อก/เทคนิค (H P S B R V G)/undo-redo; แก้ตรงไหนล็อกตรงนั้น สร้างแทปใหม่ได้โดยไม่ทับงานที่แก้

### เพิ่มใน Phase 4
- **คอร์ด**: BTC บน instrumental → smoothing ตาม beat grid → slash chord จากย่านเบส (heuristic) แก้ชื่อคอร์ดเองได้
- **โครงสร้างเพลง**: แบ่งห้อง, ตรวจเปลี่ยนคีย์กลางเพลง, แบ่งท่อน (Intro/Verse/Chorus/...) แบบ heuristic — เปลี่ยนชื่อ/แก้ได้
- **เนื้อร้อง**: ถอดเสียงด้วย faster-whisper (timestamp ระดับคำ) หรือวางเนื้อเองแล้วจัดเวลาให้ (เทียบลำดับตัวอักษรกับผล ASR ไม่ใช่ forced alignment)
- **Chord Sheet**: โหมดใหม่ แสดงท่อน/คอร์ดเหนือคำร้อง, ไดอะแกรมคอร์ด, transpose + capo; แถบท่อน/คอร์ด/เนื้อบน Piano Roll
- **เครื่องมือซ้อม**: Metronome ตาม beat grid จริง, **count-in** 1/2/4 จังหวะ, **ช้าลง 50–110% โดยไม่เพี้ยนเสียง** (SoundTouch; ครั้งแรกของแต่ละความเร็ว/stem ต้องประมวลผลสักครู่), **loop A–B**

### เพิ่มใน Phase 5
- **ตรวจ ornament จากเส้น f0**: vibrato, scoop-in, fall-off, bend-up, และความสัมพันธ์กับโน้ตถัดไป (slide / legato) — เกณฑ์ heuristic ตั้งเอง
- **ปุ่ม "เทคนิคอัตโนมัติ"** ในโหมดแทป: แปลง ornament เป็น `~ b h p /` ตามกติกาที่เล่นได้จริง (vibrato/bend ไม่อยู่สายเปล่า, bend ไม่เกิน 1.5 เสียงบนสาย 1–3 / 1 เสียงบนสาย 4–6, hammer/pull ต้องสายเดียวกันห่าง 1–4 ช่อง, slide ต้องสายเดียวกัน) — ไม่ทับที่คุณใส่เอง, undo ได้; Tab Engine เลี่ยงสายเปล่าให้โน้ตที่มี vibrato/bend
- **Export** (ปุ่ม Export บนหน้า Workspace → ไฟล์อยู่ที่ `Projects/<โปรเจกต์>/exports/`):
  - รูปแทปรายท่อน **PNG / SVG / PDF** (header, คอร์ด, แทป, เนื้อร้อง, legend) — preset 1920×1080 / 1080×1350 / 1080×1920 / A4, ธีมสว่าง/มืด/โปร่งใส, ความละเอียด 1–3×, ลายน้ำ, เลือกท่อน/ทุกท่อน/ทั้งเพลง
  - **MIDI**, **MusicXML** (โน้ตสากล+TAB, คอร์ด, เทคนิค), **Guitar Pro 5 (.gp5)**, **Text tab**, **Chord sheet (.txt)**, **LRC**, **Stems**

### เพิ่มใน Phase 6 (ทำแล้ว)
- **Model Manager** (หน้า Library): ดูโมเดลทั้งหมด สถานะ ขนาด VRAM ที่วัดจริง พื้นที่ดิสก์ และลบโมเดลที่ดาวน์โหลดอัตโนมัติ (SOME/RMVPE/BTC ติดตั้งเอง ลบจาก UI ไม่ได้)
- **Batch Mode** (หน้า Library): วาง path ไฟล์/โฟลเดอร์ ใส่คิววิเคราะห์ทีละหลายเพลง (คิวทำทีละงาน ปล่อยทิ้งข้ามคืนได้; ลิงก์ YouTube ยังไม่รองรับ)
- **Harmony Generator**: ไลน์ประสาน 3rd/6th เหนือ/ใต้เมโลดี้ตามสเกลของคีย์ (เลือกโน้ตของคอร์ดก่อนถ้ามี) ดูเป็นแทปในโหมดแทป และ export เป็น MIDI + tab
- **โหมด "ซ้อม"**: คอกีตาร์ใหญ่แสดงโน้ตปัจจุบัน/3 โน้ตถัดไปวิ่งตามเพลง (Fretboard Animation) + **Practice Mode**: เปิดไมค์/audio interface ระบบจับ pitch (McLeod NSDF) เทียบกับโน้ตที่ควรเล่น (±50 cents) ให้คะแนนต่อโน้ต (ถูก/ผิด/คนละ octave) — เทียบ pitch เท่านั้น ไม่ตรวจจังหวะละเอียด ควรใช้หูฟัง
- **Video Export**: วิดีโอ MP4 แทปวิ่งพร้อมเพลง/คอร์ด/เนื้อ (ต่อท่อนหรือทั้งเพลง) ผ่าน ffmpeg
- **แอป desktop (Tauri 2)** ใน `apps/desktop`: หน้าต่าง WebView2 ที่สตาร์ท backend ให้เองและปิดเมื่อออก — ดูหัวข้อด้านล่าง

### แอป desktop (Tauri)
```powershell
cd apps\desktop
npm install
npx tauri dev      # เปิดเป็นหน้าต่าง (ต้องมี Rust + WebView2)
npx tauri build    # ได้ตัวติดตั้ง NSIS ใน src-tauri	arget
eleaseundle
sis
```
แอปหา `backend\.venv` จากตัวแปร `MELOTAB_ROOT` หรือโฟลเดอร์ของ exe ขึ้นไปไม่เกิน 6 ชั้น แล้วรัน uvicorn ให้เอง (สตาร์ทแบบไม่บล็อกหน้าต่าง, log ที่ `%TEMP%\melotab-backend.log`; ถ้าพอร์ต 8000 มี backend อยู่แล้วจะไม่เริ่มซ้ำ) · ทดสอบ exe 3 รอบ: backend พร้อมใน 1–2 วินาที, CORS ของ `tauri.localhost` ผ่าน, ปิดหน้าต่างแล้ว backend หยุดครบ (ไม่เหลือโปรเซส) · ปิดหน้าต่างปกติแล้ว backend ที่แอปสตาร์ทไว้หยุดตาม · **ตัวติดตั้ง (~1.7 MB) ยังไม่ได้รวม Python/PyTorch/โมเดล (หลาย GB)** — ต้องมีโฟลเดอร์โปรเจกต์ที่ตั้ง environment ไว้แล้ว

### ข้อจำกัดที่รู้ (Phase 1–6)
- ยังไม่มีเลขนิ้ว, ไม่มีโน้ตสากล/ชื่อโน้ตในรูป export; เทคนิคอัตโนมัติเป็น heuristic ยังไม่ได้วัดกับเพลงที่แกะมือ (ตรวจและแก้เองเสมอ)
- Export: ความยาวโน้ตใน MusicXML/GP ปัดเป็น 1/16 และไม่มี tie ข้ามห้อง (ส่วนที่เหลือเป็นพัก), 1 beat = ตัวดำเสมอ, ไฟล์เป็น GP5 (ไม่ใช่ .gp ของ GP8) และยังไม่ได้เปิดทดสอบใน Guitar Pro/MuseScore จริง (ตรวจเขียน→อ่านกลับด้วยไลบรารีเท่านั้น), Video export ใช้ CPU วาดเฟรม (เวลาเรนเดอร์ ~ ความยาววิดีโอ) ไม่มีโน้ตสากลในวิดีโอ
- Block ยังไม่ใช่ CAGED แท้ และยังไม่แยกตามท่อนเพลง; น้ำหนักความยากเป็น heuristic ที่ยังไม่ปรับกับนักกีตาร์จริง
- ความถูกต้องของโน้ตตรวจด้วยการฟังเทียบบน 2 เพลงเท่านั้น ยังไม่มี ground truth; คอร์ด (BTC ไม่ให้ confidence)/ท่อน/เนื้อร้อง (Whisper ถอดเสียงร้องไทยพลาดได้) ยังไม่เคยวัดกับของจริง → ตรวจและแก้เองเสมอ
- ท่อนแบ่งด้วย heuristic ไม่ใช่ allin1; ไม่มี time signature แยกจากการนับ beat; ช้าลงใช้ buffer ที่ยืดไว้ล่วงหน้า (กินหน่วยความจำเพิ่มต่อความเร็ว)
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

- Practice Mode ทดสอบด้วยไมค์ปลอม (เสียง 440 Hz) กับหน่วยทดสอบ pitch เท่านั้น ยังไม่ได้ลองกับกีตาร์จริง; Harmony ยังไม่ได้ฟังตรวจกับเพลงจริง; ยังไม่มี TensorRT/ONNX
