# สถานะโปรเจกต์ MeloTab (เขียนทับทุกครั้งที่จบงาน)

**อัปเดตล่าสุด**: 2026-10-03
**Phase ปัจจุบัน**: ยังไม่เริ่ม (ขั้นออกแบบเสร็จแล้ว → ถัดไปคือ Phase 0)

## ทำเสร็จแล้ว
- [x] เขียนแผนออกแบบ `plan.md` (25 หัวข้อ + ภาคผนวก)
- [x] อ่านและทำความเข้าใจแผนทั้งหมดร่วมกับ Claude
- [x] ตั้งระบบบันทึกความคืบหน้า (`CLAUDE.md`, `.claude/`)
- [x] commit แรก (plan + CLAUDE.md + .claude/)
- [x] เพิ่ม .gitignore, backend/requirements.txt (ยังไม่ pin/ไม่ได้ทดสอบ), README.md — ยังไม่ commit

## กำลังทำ
- (ไม่มี)

## ทำต่อ (ลำดับถัดไป)
- [x] Phase 0 — ตั้ง Python env (backend/.venv) + PyTorch cu130 + ชุดแกน (CUDA ใช้ได้, pip check ผ่าน) ยังไม่ commit
- [ ] Phase 0 — สร้างโครงสร้างโฟลเดอร์ repo ตามหัวข้อ 21
- [x] Phase 0 — ลองติดตั้งตัวเสี่ยงใน .venv-spike: beat-this/faster-whisper/whisperx/pythainlp ผ่าน; essentia/madmom ล้มบน Windows; allin1 import ไม่ได้ (ดู DECISIONS.md) — ยังไม่ commit
- [ ] Phase 0 — ยังไม่ได้ลอง: RMVPE (ต้องดึง repo+weights), SOME, ROSVOT, BTC; แก้ madmom/allin1 หรือหาทางเลือก
- [ ] Phase 0 — รัน separation + f0 บนเพลงจริง วัด VRAM/เวลา
- [ ] Phase 0 — spike ทดสอบโมเดลทีละตัว: separation, RMVPE, torchcrepe, SOME, Beat This!, essentia, BTC, faster-whisper
- [ ] Phase 0 — วัดเวลา/VRAM จริง แล้วอัปเดตตารางใน plan.md หัวข้อ 18
- [ ] Phase 0 — เตรียมชุดเพลงทดสอบ 10–20 เพลงที่แกะมือไว้ (ground truth)
- [ ] Phase 0 Done: รันสคริปต์เดียว ได้ MIDI เมโลดี้จากลิงก์ YouTube

## Roadmap (ติ๊กเมื่อผ่านเกณฑ์ "Done" ใน plan.md หัวข้อ 23)
- [ ] Phase 0 — Setup & Spike
- [ ] Phase 1 — MVP หลังบ้าน + หน้าบ้านพื้นฐาน
- [ ] Phase 2 — ความแม่นยำ (สำคัญสุด)
- [ ] Phase 3 — Tab Engine + Editor
- [ ] Phase 4 — ทฤษฎีดนตรีครบ + Chord Sheet + Metronome
- [ ] Phase 5 — เทคนิคกีตาร์ + Export
- [ ] Phase 6 — ขัดเกลา & ฟีเจอร์เสริม

## Blocker / คำถามค้าง
- (ไม่มี)

## หมายเหตุ
- plan.md อ้างว่าอยู่ที่ `docs/plan.md` แต่ตอนนี้อยู่ที่รากโปรเจกต์ — ตัดสินใจย้ายหรือแก้แผนภายหลัง
- git ยังไม่มี commit และ `plan.md` ยัง untracked
