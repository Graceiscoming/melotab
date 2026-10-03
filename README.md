# 🎸 MeloTab

โปรแกรม Desktop (รัน local ทั้งหมด) สำหรับมือกีตาร์สายเมโลดี้
**วางลิงก์ YouTube หรือไฟล์เสียง → แกะเมโลดี้เสียงร้อง → Piano Roll → Guitar Tab → Export เป็นรูปรายท่อน**

หลักการ: **ความแม่นยำของโน้ตมาก่อนความเร็ว** และ **คนตรวจ/แก้ได้ง่ายที่สุด** (Human-in-the-loop)

## สถานะปัจจุบัน

> 🚧 **Phase 0 (Spike) จบแล้ว — ยังไม่มีแอปที่ใช้งานได้ มีแค่สคริปต์ทดลองใน `backend/scripts/`**

| Phase | เนื้อหา | สถานะ |
|---|---|---|
| 0 | Setup & Spike (ทดสอบโมเดลทีละตัว วัด VRAM/เวลา) | ✅ จบ (เหลือ 2 ข้อยกไป Phase 1 ดูด้านล่าง) |
| 1 | MVP หลังบ้าน + Piano Roll พื้นฐาน | ⏳ ถัดไป |
| 2 | ความแม่นยำของโน้ต | ⏳ |
| 3 | Tab Engine + Editor | ⏳ |
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

## การติดตั้ง
ยังไม่พร้อมใช้งาน — จะเขียนขั้นตอนจริงหลังจบ Phase 0 เมื่อทดสอบแล้ว

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
backend/requirements.txt
```

## ข้อควรระวัง
- ใช้เพื่อการเรียน/ส่วนตัว — ตรวจลิขสิทธิ์เพลงและเงื่อนไข YouTube ก่อนเผยแพร่แทป
- บางโมเดลเป็น non-commercial ต้องตรวจ license ก่อนแจกจ่าย/ขาย
