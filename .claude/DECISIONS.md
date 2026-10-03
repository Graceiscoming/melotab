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

## 2026-10-03 — Spike SOME (Singing-Oriented MIDI Extractor)
- ที่มา: https://github.com/openvpi/SOME (MIT) clone ไว้ที่ `third_party/SOME` (gitignore); น้ำหนัก `v1.0.0-baseline` → `models/SOME/0119_continuous256_5spk/model_ckpt_steps_100000_simplified.ckpt` (ดาวน์โหลดจาก GitHub release ด้วย gh)
- ติดตั้ง: **ไม่ใช้ `requirements.txt` ของ repo** (pin fairseq==0.12.2, gradio 3.47.1, onnx==1.14.0, librosa<0.10 ซึ่งน่าจะล้มบน Py3.11/Windows) — ลงเฉพาะที่ infer ใช้ใน `.venv-spike`: click, lightning, mido, h5py, matplotlib, torchmetrics, praat-parselmouth, PyYAML, tqdm, einops, librosa → รันได้ torch 2.8.0+cu128 ยังใช้ CUDA ได้ `pip check` ผ่าน
- รัน: `python infer.py --model CKPT --wav vocal.wav --midi out.mid` ใช้เวลาไม่กี่วินาที (progress 3 batch ~1.5 s) บน vocal stem 49 s; **ยังไม่ได้วัด VRAM ของ SOME แยก**
- config ของโมเดลอ้าง RMVPE (`pretrained/rmvpe/model.pt`) แต่ infer ทำงานได้โดยไม่มีไฟล์นี้ (ไม่ error) — ยังไม่ได้ตรวจว่ามีผลต่อคุณภาพหรือไม่
- **ผลบน song01** (`backend/scripts/spike_some_eval.py`): 150 โน้ต, median 278 ms (min 104 ms, max 0.81 s), ช่วง D♯3–D♯5
  - เทียบกับ median f0 (torchcrepe) ในช่วงโน้ต: mean|d| = 0.35 semitone, ภายใน ±0.5 = 85%, ±1 = 93%, octave error = 0
  - ครอบคลุม voiced frames 93%; frames ในโน้ตที่เป็น unvoiced 8%; โน้ตที่ไม่มี voiced f0 เลย 1 ตัว
  - **ข้อควรระวัง**: ตัวเลขนี้วัดเทียบกับ f0 ของ torchcrepe (ไม่ใช่ ground truth จริง) จึงบอกได้แค่ว่า "สอดคล้องกับเส้น pitch" ไม่ได้บอกว่าแบ่งโน้ต/ onset ถูก
- ไฟล์ฟังเทียบ `testdata/out/compare_some.wav` (ซ้าย=vocal, ขวา=โน้ต SOME) — ผู้ใช้ฟังแล้ว: ตรงดี (เพลงเดียว ยังไม่ครอบคลุมสไตล์อื่น)
- หมายเหตุ: MIDI ที่ออกมาใช้ tempo เริ่มต้นของ SOME (ยังไม่ผูกกับ beat grid จริง) เวลาในไฟล์เป็นวินาทีผ่าน mido ใช้ได้

## 2026-10-03 — วัดเพลงเต็ม song02 (290 s = 4:50, mp3 ผู้ใช้โหลดมาเอง)
| ขั้น | เวลา | VRAM เพิ่ม |
|---|---|---|
| Separation (Mel-Band RoFormer, โมเดลโหลดไว้แล้ว) | 34.0 s (≈0.12× realtime) | ≈ 3.77 GB (peak รวม 4.64 GB) |
| f0 torchcrepe full+viterbi | 13.4 s | ≈ 1.79 GB |
| SOME (โหลดโมเดล+infer ทั้งโปรเซส) | 9.7 s wall | ≈ 1.2 GB (peak รวม 1.8 GB, วัดด้วย nvidia-smi) |
- รวม GPU ≈ 57 s ต่อเพลง 4:50 (ยังไม่รวม ffmpeg/ดาวน์โหลด/โหลดโมเดลครั้งแรก ~70 s) → ดีกว่าประมาณการ 1.5–3 นาทีใน plan.md (ยังไม่รวมขั้น karaoke/de-reverb/beat/chord/lyrics)
- VRAM ไม่โตตามความยาวเพลง (chunking ทำงานตามคาด) peak รวมทุกขั้น < 5 GB จากที่มี 8 GB → รันทีละโมเดลพอ
- **ข้อสังเกตสำคัญ — SOME บน song02**: 807 โน้ต (median 244 ms, min 34 ms); เทียบ median f0: mean|d| = 1.67 st, ±1 st = 81%, ต่างกัน ≥ 11 semitone **63 โน้ต** (44 ตัวพอดี +12) ส่วนใหญ่ SOME ให้ A3/B3/D3/C♯4/F♯3 ขณะ f0 บอกสูงกว่า 1 octave (เช่น 67.9–70.5 s ต่อเนื่องหลายโน้ต SOME=A3 f0=A4)
  - อาจเป็น SOME พับ octave ในช่วงเสียงสูง หรือ torchcrepe กระโดด octave — **ยังไม่รู้ว่าฝั่งไหนผิด ต้องฟัง** (`testdata/out2/compare_some.wav`, ฟังช่วง ~66–71 s, 83–84 s, 130–150 s, 160–180 s)
  - ช่วงเสียง SOME รวม G2–F♯5 ขณะ f0 (2–98 percentile) A3–E5 → โน้ต G♯2 ฯลฯ น่าสงสัย
  - บทเรียน: เพลง 49 วินาทีแรกไม่เจอปัญหานี้ → ต้องมีชุดทดสอบหลายเพลง และ plan.md หัวข้อ 7 (ensemble f0 + แก้ octave ด้วยบริบท) มีเหตุผลจริง
- ถ้า SOME เป็นฝ่ายผิด: แนวแก้ = ใช้ f0 ensemble ตัดสิน octave ของโน้ต (แก้โน้ตของ SOME ให้ตรง octave ของ median f0) หรือลอง ROSVOT/HMM ของเราเอง

## 2026-10-03 — Spike RMVPE (เทียบ torchcrepe, song02)
- ที่มา: น้ำหนัก `rmvpe.zip` จาก https://github.com/yxlllc/RMVPE (release 230917) → `models/RMVPE/model.pt`; ใช้คลาส RMVPE ที่อยู่ใน `third_party/SOME/modules/rmvpe` (ไม่ต้องลงแพ็กเกจเพิ่ม); สคริปต์ `backend/scripts/spike_rmvpe.py` (รันด้วย `.venv-spike`)
- ความเร็ว/VRAM บน 290 s: โหลด 0.8 s, infer **1.9 s** (เร็วกว่า torchcrepe 13.4 s มาก), VRAM เพิ่ม ≈ 3.5 GB (วัดด้วย NVML อาจรวม cache ของ allocator; ยังไม่ได้จูน)
- voiced: RMVPE 75% / crepe 79% / ตรงกันทั้งคู่ 70%
- ในเฟรมที่ voiced ทั้งสองตัว: median ต่าง −0.02 semitone, ต่าง < 0.5 st = 92.9%, ต่าง octave (≥11 st) 1.06% (215 เฟรม) → สองตัวเห็นตรงกันเกือบทั้งหมด
- **โน้ต 63 ตัวที่ SOME ต่างจาก crepe ≥ 1 octave**: RMVPE ตรงกับ crepe ใน **55 ตัว**, ต่างจากทั้งคู่ 8 ตัว, ตรงกับ SOME 0 ตัว (เช่น 67.9–70 s: SOME=A3/B3/C♯4, crepe=RMVPE=A4/B4/C♯5)
  - ข้อสรุปเบื้องต้น: **SOME น่าจะพับ octave ลงในช่วงเสียงสูง** เพราะ f0 สองโมเดลอิสระเห็นตรงกัน (ยังไม่ใช่ข้อสรุปแน่ชัด — ต้องให้ผู้ใช้ฟังช่วง ~66–71 s ยืนยัน และ 8 ตัวที่ต่างจากทั้งคู่ยังไม่ได้ตรวจ)
  - SOME vs RMVPE ทั้งเพลง: mean|d| = 1.79 st, ±1 st = 79%, ต่าง octave 73/796 โน้ต
- แนวทางสำหรับ Phase 2: ใช้ f0 ensemble (RMVPE + crepe) เป็นตัวตัดสิน octave ของโน้ตจาก SOME (แก้โน้ตที่ median f0 ต่างจากโน้ต ≈ ±12 st ให้ตรง octave ของ f0) และ RMVPE เร็วกว่ามากจึงเหมาะเป็น f0 หลัก

## 2026-10-03 — Spike Beat This! (song02, 4:50, ใช้ mix เต็ม)
- ใช้ `beat-this` 1.1.0 (`File2Beats`, checkpoint `final0` ~77 MB ดาวน์โหลดอัตโนมัติไป `~/.cache/torch/hub/checkpoints/`), `dbn=False`, device cuda, สคริปต์ `backend/scripts/spike_beats.py` (รันด้วย `.venv-spike`)
- ความเร็ว/VRAM: infer **1.3 s** / 290 s, VRAM เพิ่ม ≈ 0.52 GB (ดาวน์โหลด+โหลดโมเดลครั้งแรก 17.9 s)
- ได้ 437 beats, 126 downbeats; beat แรกที่ 0.14 s
- **ปัญหาที่เจอ — tempo กระโดดครึ่ง/เท่าตัว**: BPM ต่อช่วง 30 s สลับระหว่าง ≈ 128–130 กับ ≈ 63.8 (60–150 s, 210–240 s, 270+ s เป็น ≈ 63.8) → BPM median 125.0 แต่ std 62 (ไม่น่าเชื่อถือ), beats ต่อห้อง: 4 ตัว 82 ห้อง, 2 ตัว 29 ห้อง, 3 ตัว 8 ห้อง, อื่นๆ น้อย
  - สมมติฐาน (ยังไม่ได้ฟังยืนยัน): เพลงจริงน่าจะ ≈ 128 BPM แล้วโมเดลวาง beat แบบ half-time ในบางท่อน (ห้องละ 2 beat) → ต้องมีขั้น **tempo normalization** (รวมเป็น tempo เดียวต่อท่อน/ทั้งเพลง) และ UI ให้ผู้ใช้กด ×2 / ÷2 ได้ (plan.md หัวข้อ 6 ขั้น [3] ควรเพิ่มข้อนี้)
  - ไฟล์ฟัง `testdata/out2/beats_click.wav` (ซ้าย = เพลง, ขวา = คลิก: downbeat สูง / beat ต่ำ) รอผู้ใช้ฟังยืนยันว่าคลิกตรงจังหวะไหม และท่อนไหนเป็น half-time
- Beat This! เบามาก (0.5 GB / 1.3 s) → รันบน GPU ขนานกับงานอื่นได้สบาย
