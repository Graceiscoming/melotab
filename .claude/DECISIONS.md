# บันทึกการตัดสินใจ (Decision Log)

รูปแบบ: วันที่ — หัวข้อ → ตัดสินใจอะไร, เพราะอะไร, ทางเลือกที่ไม่เลือก
ผลวัดจริง (VRAM/เวลา/ความแม่น) จดไว้ที่นี่ด้วย

---

## 2026-10-03 — ตั้งแผนเริ่มต้น
- **สถาปัตยกรรม**: Tauri 2 + React/TS (frontend) + Python FastAPI sidecar (backend)
  - เหตุผล: งาน AI/เสียงอยู่ Python (ecosystem ครบ), UI อยู่เว็บ (กราฟิกลื่น), Tauri เบากว่า Electron
- **รันแบบ local ทั้งหมด**: ใช้ GPU เต็มที่ ไม่มีค่า cloud รายเดือน
- **แบบจำลองโน้ตแทป**: เก็บเป็น event + `start_beat` ไม่ใช่ text → แก้ตัวเดียวไม่กระทบตัวอื่น
- **Fingering**: Viterbi/DP ด้วย Numba
- (ชื่อโมเดลเฉพาะเจาะจง เช่น RMVPE/SOME/Beat This! ยังเป็นตัวเลือกตามแผน — ยืนยันหลัง Phase 0 spike)

## 2026-10-03 — ตั้ง environment Phase 0
- **เครื่องจริง**: Python 3.11.9, ffmpeg 9.0, driver NVIDIA 610.74, RTX 4060 8GB, ดิสก์ D: ว่าง 531 GB, node 26.7, cargo 1.97 (พร้อมสำหรับ Tauri)
- **PyTorch**: ใช้ `2.14.1+cu130` (index cu130) — `torch.cuda.is_available()` = True บนเครื่องนี้
  - เหตุผล: driver ใหม่ รองรับ CUDA 13; cu128 ล่าสุดแค่ torch 2.11 จึงเลือก cu130
- **venv**: `backend/.venv` (Python 3.11) — ถูก gitignore
- **ลงแล้ว (ชุดแกน Phase 0)**: torch, torchaudio, numpy 2.4.6, scipy, librosa 0.11, soundfile, pyloudnorm, yt-dlp, torchcrepe, numba, psutil, nvidia-ml-py, pytest, audio-separator[gpu] 0.47.0 (onnxruntime-gpu 1.30: มี CUDA + TensorRT provider)
- `pip check` ไม่พบ conflict; `backend/requirements-lock.txt` = `pip freeze` ของชุดที่ใช้ได้จริง (ยังเป็นแค่ชุดแกน)
- **ยังไม่ได้ลง/ทดสอบ (ตัวเสี่ยง)**: essentia, allin1/madmom/natten, whisperx, RMVPE, SOME, ROSVOT, Beat This!, BTC — ต้องลองแยกทีละตัว
- **ยังไม่ได้ทดสอบรันจริง**: ยังไม่ได้รัน separation / f0 บนไฟล์เสียงจริง และยังไม่ได้วัด VRAM/เวลา

## 2026-10-03 — Spike ติดตั้งตัวเสี่ยง (venv แยก `backend/.venv-spike`)
ผล (ทดสอบแค่ "ติดตั้ง + import" ยังไม่ได้รันโมเดลจริง):
| แพ็กเกจ | ผล | หมายเหตุ |
|---|---|---|
| Beat This! (`beat-this` 1.1.0, จาก GitHub zip) | ✅ ติดตั้ง+import ผ่าน | ยังไม่ได้รันบนเสียง |
| faster-whisper 1.2.1 | ✅ ผ่าน | ยังไม่ได้โหลดโมเดล |
| whisperx 3.8.6 | ✅ ผ่าน แต่ **ดึง torch ลงเป็น 2.8.0+cpu** | แก้ด้วย `pip install --force-reinstall --no-deps torch==2.8.0 torchaudio==2.8.0 --index-url .../cu128` → CUDA ใช้ได้ |
| pythainlp 5.3.8 | ✅ ผ่าน | |
| essentia | ❌ build ไม่ผ่านบน Windows | ใช้ librosa chroma เป็น fallback หรือย้ายไป WSL2 |
| madmom | ❌ build ไม่ผ่าน (`invalid mode 'rUb'`, Python 3.11) | |
| allin1 1.1.0 | ⚠️ ติดตั้งได้แต่ import ไม่ได้ (ต้องใช้ madmom; natten ไม่ได้ลง) | ต้องแก้ madmom ก่อน หรือหาทางเลือกทำ section labels |
| RMVPE | ❓ ไม่มีบน PyPI | ต้องดึงโค้ด+น้ำหนักจาก repo เอง ยังไม่ได้ทำ |
| SOME / ROSVOT / BTC | ❓ ยังไม่ได้ลอง | |

**ข้อสรุปสำคัญ**
- **whisperx (และอาจรวมถึงแพ็กเกจที่ pin torch) ทำให้ torch เปลี่ยนเป็นรุ่น CPU เงียบๆ** → หลังลงอะไรก็ตามต้องเช็ก `torch.cuda.is_available()` ทุกครั้ง
- torch ของ venv หลัก (2.14.1+cu130) กับ whisperx (ต้องการ 2.8.x) ไม่เข้ากัน → ถ้าจะใช้ whisperx ใน venv หลักต้องลดเป็น torch 2.8.0+cu128 ทั้ง venv หรือแยก lyrics เป็น worker/venv ของตัวเอง (ตัดสินใจภายหลัง)
- `backend/requirements-spike-lock.txt` = freeze ของ venv ทดลอง

## 2026-10-03 — ผลวัดจริงครั้งแรก (เพลงทดสอบ song01, 48.9 วินาที, ผู้ใช้โหลดมาเอง เพราะ yt-dlp 403 / cookies Chrome-Edge อ่านไม่ได้)
เครื่อง: RTX 4060 Laptop 8GB, torch 2.14.1+cu130 (venv หลัก) — สคริปต์: `backend/scripts/spike_separation.py`, `spike_f0.py`
| ขั้น | โมเดล | เวลา | VRAM เพิ่ม (peak − base) |
|---|---|---|---|
| Separation | `vocals_mel_band_roformer.ckpt` (audio-separator) | โหลด 70.5 s (รวมดาวน์โหลดโมเดลครั้งแรก), แยก 18.3 s (≈0.37× realtime) | ≈ 3.8 GB (peak รวม ≈ 4.6 GB) |
| f0 | torchcrepe full + viterbi, hop 10 ms | 2.6 s | ≈ 1.7 GB (peak รวม ≈ 2.55 GB) |
- ผลสอดคล้องกับตาราง budget ใน plan.md หัวข้อ 18 (separation 3–6 GB, f0 1–2 GB) แต่เป็นเพลงสั้น 49 วินาที; **เพลง 4 นาทีต้องวัดใหม่** (เวลา ≈ ×5; VRAM น่าจะใกล้เดิมเพราะ chunk)
- f0: voiced 87% (threshold periodicity 0.21 ค่าเริ่มต้น อาจรวมเสียงลม/พยัญชนะ ต้องจูนตอนทำ voicing detection), ช่วงเสียง F♯3–C♯5 median F♯4, โน้ตที่พบบ่อย C♯4 F♯4 G♯4 A♯4 D♯4 → น่าจะเป็นคีย์ F♯ major / D♯ minor (เป็นแค่ข้อสังเกตจากฮิสโทแกรม ยังไม่ได้วิเคราะห์ key จริง)
- **ยังไม่ได้ตรวจความถูกต้องของโน้ต** (ไม่มี ground truth, ยังไม่ได้ฟังเทียบ), ยังไม่ได้ทดสอบ RMVPE/karaoke/de-reverb
- โมเดลเก็บที่ `D:\melotab\models\` (gitignore); ไฟล์ทดสอบที่ `testdata/` (ไฟล์เสียงถูก gitignore)
- หมายเหตุ: ต้องตั้ง `PYTHONIOENCODING=utf-8` เมื่อพิมพ์ชื่อโน้ตที่มี ♯ บน Windows console
