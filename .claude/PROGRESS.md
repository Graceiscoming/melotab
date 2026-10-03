# สถานะโปรเจกต์ MeloTab (เขียนทับทุกครั้งที่จบงาน)

**อัปเดตล่าสุด**: 2026-10-04
**Phase ปัจจุบัน**: Phase 6 (ขัดเกลา & ฟีเจอร์เสริม — ต่อเนื่อง) ทำบางส่วนแล้ว — Phase 0–5 จบแล้ว

## ทำต่อ (session หน้า)
- **แก้ก่อน**: Tauri สตาร์ท backend อัตโนมัติยังไม่เสถียร (รอบสองไม่ขึ้นใน 50 s) → spawn แบบไม่บล็อก setup + ทดสอบ exe ซ้ำหลายรอบ
- Phase 6 ที่เหลือ: TensorRT/ONNX (วัดก่อนว่าคุ้ม — ตอนนี้ pipeline 4:50 ใช้ GPU ~57 s), ตัวติดตั้งที่รวม Python/โมเดล (หรือตัวช่วยตั้ง environment ครั้งแรก), ดาวน์โหลด/ตรวจโมเดลจาก Model Manager, YouTube ดาวน์โหลด (ติด 403)
- ค้างจาก Phase 4–5: วัดคอร์ด/ท่อน/เนื้อ/ornament กับ ground truth จริง, เปิดไฟล์ .gp5/.musicxml ใน Guitar Pro/MuseScore จริง, โน้ตสากล+เลขนิ้วในรูป export, UI เลือกช่วง export ด้วยการลาก
- ลองกับของจริง: Practice Mode ด้วยกีตาร์/ไมค์จริง, ฟังไลน์ประสาน, ฟังเสียง slow-down

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
- [x] Phase 1 — โครงสร้าง backend/melotab (config, gpu, audio, pipeline, song, cli) + เทสต์ตรรกะ
- [x] Phase 1 — CLI `python -m melotab.cli analyze` ไฟล์เสียง → song.json + melody.mid (ลิงก์ YouTube ยังไม่ได้: ติด 403)
- [x] Phase 1 — Job orchestrator + cache content-hash + WebSocket progress + system monitor (FastAPI) — ทดสอบจริงแล้ว (ดู DECISIONS.md)
- [x] Phase 1 — Project save/load พื้นฐาน (โฟลเดอร์ + PUT /song); **ย้ายไป Phase 2/6**: SQLite index, autosave, history, .melotab
- [x] Phase 1 — Frontend: React+Vite, Import, Piano Roll (PixiJS) + เล่นเสียง/playhead, Status bar (ตรวจด้วย Chrome จริงแล้ว)
- [x] Phase 1 — รวม environment: SOME/BTC/Beat This! ใช้ได้ใน `.venv` หลัก (torch 2.14) แล้ว; whisperx เลื่อนไป Phase 4
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
- [x] Phase 1 — MVP หลังบ้าน + หน้าบ้านพื้นฐาน
- [x] Phase 2 — ความแม่นยำ (สำคัญสุด) (ยังไม่ได้วัด Note F1 กับ ground truth จริง ต้องมี MIDI ที่แกะมือ)
- [x] Phase 3 — Tab Engine + Editor (น้ำหนักต้นทุน/ความยากยังไม่ปรับกับนักกีตาร์จริง; editor ยังขาด time-nudge/ripple/คลิกขวา/finger)
- [x] Phase 4 — ทฤษฎีดนตรีครบ + Chord Sheet + Metronome (คอร์ด/ท่อน/เนื้อยังไม่วัดกับ ground truth; ไม่ใช้ allin1/WhisperX)
- [x] Phase 5 — เทคนิคกีตาร์ + Export (heuristic ยังไม่วัดกับ ground truth; GP5/MusicXML ยังไม่เปิดใน Guitar Pro/MuseScore จริง)
- [~] Phase 6 — ขัดเกลา & ฟีเจอร์เสริม: ทำแล้ว Tauri shell/Model Manager/Batch/Harmony/Fretboard animation/Practice Mode/Video export; เหลือ TensorRT/ONNX, ตัวติดตั้งที่รวม Python+โมเดล, Harmony/Practice ลองกับของจริง

## Blocker / คำถามค้าง
- (ไม่มี)

## หมายเหตุ
- plan.md อ้างว่าอยู่ที่ `docs/plan.md` แต่ตอนนี้อยู่ที่รากโปรเจกต์ — ตัดสินใจย้ายหรือแก้แผนภายหลัง
- git ยังไม่มี commit และ `plan.md` ยัง untracked
