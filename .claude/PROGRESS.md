# สถานะโปรเจกต์ MeloTab (เขียนทับทุกครั้งที่จบงาน)

**อัปเดตล่าสุด**: 2026-10-03
**Phase ปัจจุบัน**: Phase 0 จบ (ผู้ใช้ตัดสินใจข้ามการทดสอบเพิ่ม) → ถัดไปคือ Phase 1

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
- [ ] **ยกไป Phase 1**: โครงสร้างโฟลเดอร์ repo ตามหัวข้อ 21 (ตอนนี้มีแค่ backend/scripts)
- [ ] **ยกไป Phase 1**: สคริปต์เดียว ไฟล์เสียง/ลิงก์ → MIDI เมโลดี้ (เกณฑ์ Done ของ Phase 0 ที่ยังไม่ครบ; YouTube ติด 403 ใช้ไฟล์ที่โหลดเองไปก่อน)
- [ ] **ยกไป Phase 1**: รวม environment — SOME/BTC/Beat This! รันใน `.venv-spike` (torch 2.8) ยังไม่ได้ย้ายมา `.venv` หลัก (torch 2.14); ต้องตัดสินใจเรื่อง torch เวอร์ชันเดียว (whisperx ต้องการ 2.8)
- [ ] **ยกไป Phase 2**: ROSVOT, essentia/allin1 (ลงไม่ผ่านบน Windows), เทียบ karaoke model ตัวอื่น, ทดสอบเพลงยาก/ประสานแน่น, ground truth ของจริง
- [x] Phase 0 — ลองติดตั้งตัวเสี่ยงใน .venv-spike: beat-this/faster-whisper/whisperx/pythainlp ผ่าน; essentia/madmom ล้มบน Windows; allin1 import ไม่ได้ (ดู DECISIONS.md) — ยังไม่ commit
- [ ] Phase 0 — ยังไม่ได้ลอง: RMVPE (ต้องดึง repo+weights), SOME, ROSVOT, BTC; แก้ madmom/allin1 หรือหาทางเลือก
- [x] Phase 0 — รัน separation + f0 บนเพลงจริง (song01, 49 s): แยก 18 s / 3.8 GB, f0 2.6 s / 1.7 GB (ดู DECISIONS.md) — ยังไม่ commit
- [x] Phase 0 — ฟังเทียบ f0 (torchcrepe) บน song01: ผู้ใช้ฟังแล้วตรงดี
- [x] Phase 0 — SOME รันได้ (150 โน้ต, สอดคล้อง f0 ±1 semitone 93%) — ผู้ใช้ฟัง compare_some.wav แล้ว ตรงดี; ยังไม่ commit
- [x] Phase 0 — วัดเพลงเต็ม song02 (4:50): GPU รวม ≈ 57 s, peak VRAM < 5 GB (ดู DECISIONS.md)
- [x] Phase 0 — ปัญหา SOME ต่าง octave **แก้ได้ด้วย karaoke model** (63 → 1 → 0 โน้ต) สาเหตุคือเสียงประสานใน vocal stem — รอผู้ใช้ฟังยืนยัน cmp_dry.wav
- [x] Phase 0 — RMVPE ลองแล้ว: เร็ว (1.9 s/290 s) ตรงกับ crepe ในโน้ตที่ SOME ต่าง octave 55/63 → SOME น่าจะผิด; ยังไม่ commit
- [x] Phase 0 — Beat This! รันจริงแล้ว: เร็ว (1.3 s) แต่ tempo กระโดด ≈128↔64 BPM ต้องมี tempo normalization — รอผู้ใช้ฟัง beats_click.wav; ยังไม่ commit
- [x] Phase 0 — BTC รันได้ (คอร์ด diatonic D major ครบ, flicker 53/175 ช่วง ต้อง smoothing) — รอผู้ใช้ตรวจคอร์ด; ยังไม่ commit
- [x] Phase 0 — karaoke + de-reverb ลองแล้ว (ช้า: 118 s + 67 s ต่อเพลง 4:50) — ยังไม่ commit
- [x] Phase 0 — สรุปผล: อัปเดตตารางหัวข้อ 18 ใน plan.md + README
- [ ] Phase 0 — spike ทดสอบโมเดลทีละตัว: separation, RMVPE, torchcrepe, SOME, Beat This!, essentia, BTC, faster-whisper
- [ ] Phase 0 — วัดเวลา/VRAM จริง แล้วอัปเดตตารางใน plan.md หัวข้อ 18
- [ ] Phase 0 — เตรียมชุดเพลงทดสอบ 10–20 เพลงที่แกะมือไว้ (ground truth)
- [ ] Phase 0 Done: รันสคริปต์เดียว ได้ MIDI เมโลดี้จากลิงก์ YouTube

## Roadmap (ติ๊กเมื่อผ่านเกณฑ์ "Done" ใน plan.md หัวข้อ 23)
- [x] Phase 0 — Setup & Spike (จบแบบมีเงื่อนไข ดูรายการยกไปด้านบน)
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
