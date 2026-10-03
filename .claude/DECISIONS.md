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
