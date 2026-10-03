# 🎸 MeloTab — แผนพัฒนาโปรแกรมแกะเมโลดี้เสียงร้อง → Piano Roll → Guitar Tab

> เอกสารออกแบบระบบ (Design & Development Plan)
> เป้าหมาย: ลดงานแกะเพลงของมือกีตาร์สายเมโลดี้ จาก "โหลดเพลง → ฟัง → แกะ → เขียนแทป → export รูป" ให้เหลือ "วางลิงก์ → ตรวจ/แก้ → export"
> หลักการสูงสุด: **ความแม่นยำของโน้ตมาก่อนความเร็ว** และ **คนต้องตรวจและแก้ได้ง่ายที่สุด** (Human-in-the-loop)

---

## สารบัญ

1. ภาพรวมและเป้าหมาย
2. Workflow เดิม vs Workflow ใหม่
3. รายการฟีเจอร์ทั้งหมด
4. สถาปัตยกรรมระบบ
5. Tech Stack
6. Analysis Pipeline (หลังบ้าน) แบบละเอียดทีละขั้น
7. กลยุทธ์ความแม่นยำของโน้ต (หัวใจของโปรเจกต์)
8. Piano Roll Viewer
9. Chord Sheet + เนื้อร้อง + Metronome
10. Auto Guitar Tab Engine (Fingering Optimizer)
11. Block Mode (จำกัดโซนบนคอกีตาร์)
12. แปลงลูกเล่นเสียงร้อง → เทคนิคกีตาร์
13. แนะนำคีย์ที่เล่นง่าย + Capo
14. Tab Editor (จิ้มแก้ได้ทุกตัว)
15. Export ทีละท่อนเป็นรูป (และฟอร์แมตอื่น)
16. บันทึกโปรเจกต์ + Cache
17. Status / System Monitor
18. การรีดประสิทธิภาพเครื่อง i5-13500HX + RTX 4060 8GB + RAM 32GB
19. Data Model
20. API (Backend ↔ Frontend)
21. โครงสร้างโฟลเดอร์
22. ฟีเจอร์เสริมที่แนะนำเพิ่ม
23. Roadmap แบ่งเฟส
24. การทดสอบและวัดความแม่นยำ
25. ความเสี่ยงและข้อควรระวัง

---

## 1. ภาพรวมและเป้าหมาย

**MeloTab** เป็นโปรแกรม Desktop ที่รันบนเครื่องตัวเองทั้งหมด (local, ไม่ต้องพึ่ง cloud) เพื่อใช้ GPU เต็มที่และไม่มีค่าใช้จ่ายรายเดือน

สิ่งที่โปรแกรมต้องทำได้:

| # | ความสามารถ | ผลลัพธ์ |
|---|---|---|
| 1 | รับไฟล์เสียง หรือ ลิงก์ YouTube | ไฟล์ WAV คุณภาพสูง |
| 2 | แยกเสียงร้องนำออกจากดนตรี | vocal stem สะอาด |
| 3 | วิเคราะห์ทฤษฎีดนตรีทั้งเพลง | Key, Key change, Tuning, BPM, Tempo map, Time signature, ท่อนเพลง, คอร์ด |
| 4 | แกะเมโลดี้เสียงร้องให้แม่นที่สุด | โน้ตพร้อมชื่อและ octave (เช่น E4, F#4) + ค่าเพี้ยน cents |
| 5 | แสดงผลแบบ Piano Roll โน้ตวิ่ง | ดูง่าย ฟังซ้อนเทียบได้ |
| 6 | แสดง Chord Sheet แบบเว็บแจกคอร์ด | คอร์ดอยู่บน เนื้อร้องอยู่ล่าง |
| 7 | Metronome เคาะตรงจังหวะเพลงจริง | เปิด/ปิดได้ |
| 8 | สร้าง Guitar Tab อัตโนมัติ | ตำแหน่งนิ้วที่เล่นง่ายที่สุดแต่โน้ตถูก |
| 9 | Block Mode | บังคับให้แทปอยู่ในโซนคอกีตาร์ที่เลือก |
| 10 | แปลงลูกคอเป็นเทคนิคกีตาร์ | slide / bend / hammer-on / pull-off / vibrato |
| 11 | แนะนำคีย์ที่เล่นง่าย | พร้อม capo |
| 12 | Tab Editor | จิ้มตัวไหนแก้ตัวนั้นได้ทันที |
| 13 | Export ทีละท่อนเป็นรูป | PNG/SVG/PDF |
| 14 | บันทึกโปรเจกต์ + cache | เปิดกลับมาไม่ต้องประมวลผลใหม่ |
| 15 | Status / System Monitor | เห็น % งาน, GPU, VRAM, RAM, CPU ตลอดเวลา |

---

## 2. Workflow เดิม vs Workflow ใหม่

### Workflow เดิม (ทำมือ)
```
โหลด YouTube → ฟังซ้ำๆ → แกะเมโลดี้ด้วยหู → หาตำแหน่งบนกีตาร์ → เขียนแทป → แคปทีละท่อน
   (นาน, เมื่อยหู, พลาดง่ายตรงลูกคอ/โน้ตเร็ว)
```

### Workflow ใหม่
```
┌──────────────┐   ┌───────────────────┐   ┌─────────────────┐   ┌──────────────────┐
│ 1. วางลิงก์/   │──▶│ 2. กด Analyze      │──▶│ 3. ตรวจ Piano Roll│──▶│ 4. ตั้งค่าแทป       │
│   ลากไฟล์เสียง  │   │ (อัตโนมัติทั้งหมด)   │   │ ฟังเทียบ แก้โน้ต    │   │ เลือกคีย์/Block/   │
└──────────────┘   │ status บอกทุกขั้น   │   └─────────────────┘   │ เทคนิค            │
                   └───────────────────┘                          └────────┬─────────┘
                                                                           ▼
┌──────────────────┐   ┌──────────────────┐   ┌───────────────────────────────────┐
│ 7. Save โปรเจกต์   │◀──│ 6. Export ทีละท่อน │◀──│ 5. Generate Tab → จิ้มแก้ในแทป       │
│ (cache ทุกขั้น)     │   │ เป็นรูป / GP / MIDI│   │ (เล่นตามด้วย metronome / slow-down) │
└──────────────────┘   └──────────────────┘   └───────────────────────────────────┘
```

เวลาที่คาดหวังต่อเพลง 4 นาที (ประมาณการบนสเปกที่ให้มา ต้องวัดจริงอีกครั้ง):
- ดาวน์โหลด + แปลงไฟล์: ~10–30 วินาที (ขึ้นกับเน็ต)
- วิเคราะห์ทั้งหมด (ครั้งแรก): ~1.5–3 นาที
- เปิดโปรเจกต์เดิม (จาก cache): < 2 วินาที
- Generate Tab / เปลี่ยน Block / เปลี่ยนคีย์: < 0.5 วินาที (real-time)

---

## 3. รายการฟีเจอร์ทั้งหมด

### 3.1 Core (ต้องมี)
- **Input**: ลากไฟล์ (mp3, wav, flac, m4a, ogg, mp4) หรือ วางลิงก์ YouTube
- **Source Separation**: แยก Lead Vocal / Backing Vocal / Instrumental / Bass / Drums
- **Music Analysis**: Tuning offset, Key + Key change, BPM + Tempo map (รองรับเพลงที่ tempo แกว่ง), Time signature, Downbeat, ท่อนเพลง (Intro/Verse/Pre-Chorus/Chorus/Bridge/Solo/Outro), Chord (รวม slash chord เช่น C/E)
- **Melody Transcription**: โน้ตเสียงร้องพร้อม octave + cents + confidence
- **Piano Roll**: โน้ตวิ่งตามเพลง, เส้น pitch จริงซ้อน, ชื่อโน้ตบนแท่ง
- **Chord Sheet**: คอร์ดบน เนื้อร้องล่าง (แบบเว็บแจกคอร์ด) + transpose ได้
- **Metronome**: เคาะตาม beat grid จริงของเพลง (ไม่ใช่ BPM คงที่) เน้นเสียง downbeat
- **Auto Guitar Tab** + **Block Mode** + **Playability Optimizer**
- **Vocal Ornament → Guitar Technique**
- **Easy Key Suggestion** + Capo
- **Tab Editor** (random access, จิ้มแก้ตัวไหนก็ได้)
- **Export รายท่อน** เป็นรูป
- **Project Save + Cache**
- **Status Bar + System Monitor + Job Queue**

### 3.2 Practice Tools (แนะนำเพิ่ม — รายละเอียดในหัวข้อ 22)
- Slow-down โดยเสียงไม่เพี้ยน (50%–100%), Loop ท่อน, A/B compare
- Mute/Solo stem (ฟังแค่ร้อง / เอาร้องออกเหลือ backing ไว้เล่นทับ)
- Practice Mode: เสียบกีตาร์/ไมค์ แล้วโปรแกรมฟังว่าเล่นถูกไหม
- Harmony Generator (สร้างไลน์ประสานคู่ 3/6 สำหรับ twin guitar)

---

## 4. สถาปัตยกรรมระบบ

```
┌──────────────────────────────────────────────────────────────────────┐
│                     Desktop App (Tauri 2 shell)                       │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ Frontend: React + TypeScript + Vite                            │  │
│  │  ├─ Piano Roll (PixiJS / WebGL)                                 │  │
│  │  ├─ Tab Renderer + Editor (SVG, custom)                         │  │
│  │  ├─ Chord Sheet view                                            │  │
│  │  ├─ Fretboard / Block selector                                  │  │
│  │  ├─ Audio Engine (Web Audio API + AudioWorklet + Tone.js)       │  │
│  │  ├─ Status Bar / Job Panel / System Monitor                     │  │
│  │  └─ State: Zustand + Immer (undo/redo)                          │  │
│  └───────────────▲──────────────────────────────▲─────────────────┘  │
│                  │ REST (คำสั่ง)                  │ WebSocket (progress,│
│                  │                              │ system stats)       │
│  ┌───────────────┴──────────────────────────────┴─────────────────┐  │
│  │ Backend sidecar: Python 3.11 + FastAPI + Uvicorn                │  │
│  │  ├─ Job Orchestrator (DAG, queue, cancel, retry)                │  │
│  │  ├─ GPU Worker (1 process, จัดการ VRAM, โหลด/ปลดโมเดลทีละตัว)     │  │
│  │  ├─ CPU Worker Pool (ProcessPool, ใช้ core ที่เหลือ)              │  │
│  │  ├─ Analysis Modules (separation, pitch, notes, key, chord ...) │  │
│  │  ├─ Tab Engine (Viterbi fingering, block, technique) — Numba    │  │
│  │  ├─ Cache Manager (content-hash)                                │  │
│  │  ├─ Project Store (SQLite + โฟลเดอร์โปรเจกต์)                     │  │
│  │  └─ System Monitor (pynvml + psutil)                            │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                       External tools: ffmpeg, yt-dlp                   │
└──────────────────────────────────────────────────────────────────────┘
```

**ทำไมแยก Frontend / Backend แบบนี้**
- งาน AI/เสียงทั้งหมดอยู่ใน Python (ecosystem ครบที่สุด: PyTorch, librosa, essentia)
- งานแสดงผล/แก้ไข/เล่นเสียงอยู่ในเว็บเทคโนโลยี (วาดกราฟิกลื่น, UI ยืดหยุ่น)
- Tauri ทำให้เป็นแอป desktop ตัวเดียว เปิดแล้ว spawn Python sidecar ให้อัตโนมัติ
- ระหว่างพัฒนา: รันแยกเป็น `localhost` (Vite dev server + FastAPI) ได้เลย ไม่ต้อง build Tauri ทุกครั้ง

**กฎสำคัญ**: งานหนักทุกอย่างเป็น **Job แบบ async** → UI ไม่มีวันค้าง และรายงาน progress ผ่าน WebSocket เสมอ

---

## 5. Tech Stack

### 5.1 Frontend
| ส่วน | เทคโนโลยี | เหตุผล |
|---|---|---|
| Framework | React 18 + TypeScript + Vite | ecosystem ใหญ่, dev เร็ว |
| Desktop shell | Tauri 2 | เบากว่า Electron มาก, กิน RAM น้อย, รองรับ sidecar |
| State | Zustand + Immer + patches | undo/redo ง่าย |
| Piano Roll | PixiJS (WebGL) | วาดโน้ตหลายพันตัวที่ 60fps |
| Tab / Notation | SVG renderer เขียนเอง (+ alphaTab ใช้เป็นตัว export Guitar Pro/อ้างอิง) | ต้องคุมการจิ้มแก้ระดับตัวโน้ตเอง |
| Audio | Web Audio API, AudioWorklet, Tone.js, SoundTouchJS / Rubber Band (WASM) | sync เพลง+metronome แม่นระดับ sample, slow-down ไม่เพี้ยน |
| UI kit | Tailwind CSS + shadcn/ui + Radix | สวย เร็ว accessible |
| Chart system monitor | uPlot | เบามาก real-time |
| Export รูป | SVG → PNG (canvas หรือ resvg ฝั่ง backend) | คมชัดทุกความละเอียด |

### 5.2 Backend
| ส่วน | เทคโนโลยี |
|---|---|
| Runtime | Python 3.11, PyTorch 2.x + CUDA 12.x |
| API | FastAPI + Uvicorn + WebSocket |
| Download | yt-dlp + ffmpeg |
| Audio I/O | soundfile, torchaudio, pyloudnorm |
| Source separation | `audio-separator` (รวมโมเดล Mel-Band RoFormer / BS-RoFormer / MDX / Demucs), Demucs v4 htdemucs_ft |
| Vocal pitch (f0) | **RMVPE** (หลัก), **torchcrepe** full (รอง), FCPE (สำรอง/เร็ว) |
| Singing → Note | **SOME** (Singing-Oriented MIDI Extractor), ROSVOT, Basic Pitch (fallback) + HMM segmentation ของเราเอง |
| Beat / Downbeat | **Beat This!** (หลัก), madmom (สำรอง) |
| โครงสร้างเพลง | **allin1** (All-In-One: beats, downbeats, section labels) |
| Key / Tuning | essentia (KeyExtractor หลาย profile, TuningFrequency) + librosa chroma |
| Chord | BTC (Bi-directional Transformer for Chord recognition) / Chordino (NNLS-Chroma) + bass root จาก bass stem |
| Lyrics | faster-whisper large-v3 (หรือ Thai fine-tune เช่น Typhoon Whisper) + WhisperX alignment (wav2vec2 ภาษาไทย) |
| Optimization | Numba (tab engine), ONNX Runtime-GPU / TensorRT (ตัวเลือก), bf16 autocast |
| Monitor | nvidia-ml-py (pynvml), psutil |
| Storage | SQLite (index), JSON (project), FLAC (stems), NPZ (array) |
| Test/Eval | pytest, mir_eval |

> หมายเหตุ: ชื่อโมเดล/เวอร์ชันในวงการนี้อัปเดตเร็ว ก่อนเริ่ม Phase ไหนให้เช็ก leaderboard/repo ล่าสุดอีกครั้ง (เช่น MVSEP leaderboard สำหรับ separation) และออกแบบโค้ดเป็น **plugin interface** เพื่อสลับโมเดลได้โดยไม่แก้ส่วนอื่น

---

## 6. Analysis Pipeline (หลังบ้าน) แบบละเอียด

Pipeline เป็น **DAG** (งานไหนไม่ขึ้นต่อกันรันขนานกัน) — GPU รันทีละโมเดล, CPU รันงานเบาขนานไปพร้อมกัน

```
                         ┌─▶ [3] Rhythm (beats/downbeats/sections) ─┐  (CPU/GPU เบา, ใช้ mix)
[0] Ingest ─▶ [1] Prep ──┤                                          │
                         └─▶ [2] Separation (GPU หนัก)               │
                                  ├─▶ instrumental ─▶ [4] Tuning+Key ─▶ [5] Chords
                                  │                                  │
                                  └─▶ lead vocal ─▶ [6] f0 Ensemble ─▶ [7] Note Transcription
                                                     └─▶ [9] Lyrics ─┘        │
                                                                              ▼
                                                     [8] Ornament/Technique Detection
                                                                              ▼
                                                     [10] Song Model พร้อมใช้ (→ Tab Engine on demand)
```

### [0] Ingest
- ลิงก์ YouTube → `yt-dlp -f bestaudio` (ได้ opus/m4a คุณภาพสูงสุด) → เก็บ metadata (ชื่อเพลง, ศิลปิน, thumbnail, ความยาว)
- ไฟล์ local → copy เข้าโปรเจกต์
- คำนวณ **SHA-256 ของไฟล์เสียง** = key หลักของ cache (เพลงเดิมไม่ต้องทำซ้ำ)
- Progress: % การดาวน์โหลดจาก yt-dlp hook

### [1] Prep
- ffmpeg → WAV 44.1 kHz stereo float32 (สำหรับ separation)
- สร้างเวอร์ชัน mono 16 kHz (สำหรับ pitch/whisper) ภายหลังจาก stem
- วัด loudness (LUFS) และ normalize เพื่อให้โมเดลทำงานคงที่
- ตรวจ clipping / ความยาว / silence หัว-ท้าย

### [2] Source Separation (ขั้นที่สำคัญที่สุดต่อความแม่น)
ยิ่งเสียงร้องสะอาด โน้ตยิ่งแม่น จึงทำ 3 ชั้น:
1. **Vocal vs Instrumental**: Mel-Band RoFormer / BS-RoFormer (คุณภาพแยก vocal สูงสุดในกลุ่มโมเดลเปิด)
2. **Lead vs Backing vocal**: โมเดล karaoke (Mel-Band RoFormer karaoke) → ได้ **lead vocal อย่างเดียว** ตัดเสียงประสาน/คอรัสที่ทำให้ pitch tracker สับสน
3. **De-reverb / De-echo**: ลบหางเสียง reverb ที่ทำให้โน้ตลากยาวเกินจริงและ onset เบลอ
4. (ตัวเลือก) Demucs htdemucs_ft แยก bass / drums / other จาก instrumental — ใช้กับ chord (bass root) และ beat

ตั้งค่า: chunk ~8–10 วินาที, overlap 25–50%, bf16/fp16, batch ตาม VRAM
Progress: % = chunk ที่ประมวลผลแล้ว / ทั้งหมด

### [3] Rhythm & Structure (ใช้ mix เต็ม หรือ drums+bass)
- **Beat This!** → beats + downbeats (ความแม่นยำสูง, ไม่ต้องใช้ DBN post-processing)
- **Tempo map**: BPM ต่อช่วง (เพลงที่ตีสดจะแกว่ง) + BPM เฉลี่ยแสดงใน UI
- **Time signature**: จำนวน beat ระหว่าง downbeat (4/4, 3/4, 6/8, 12/8) — โหวตทั้งเพลง + เผื่อเปลี่ยนกลางเพลง
- **allin1** → section labels (intro/verse/chorus/bridge/inst/outro) — ใช้เป็น "ท่อน" สำหรับ export
- ผู้ใช้แก้ขอบเขตท่อน/ชื่อท่อนได้ (ลากเส้นแบ่งใน timeline)

### [4] Tuning + Key
- **Tuning offset**: เพลงจำนวนมากไม่ได้จูน A=440 พอดี (เช่น 432 หรือเทปเร็ว/ช้า) → วัดจาก histogram ของ f0 vocal + chroma instrumental → ได้ค่าเช่น "-18 cents" แล้วชดเชยก่อน quantize โน้ต **(สำคัญมาก ถ้าไม่ทำโน้ตจะเพี้ยนครึ่งเสียงเป็นช่วงๆ)**
- **Key**: essentia KeyExtractor หลาย profile (temperley, krumhansl, edma, bgate) + chord histogram → โหวตรวม → ผลเช่น `E major (confidence 0.87)` พร้อมตัวเลือกอันดับ 2 (relative minor C#m)
- **Key change detection**: วิเคราะห์ key แบบ sliding window ต่อท่อน → ตรวจการขึ้นคีย์ (เพลงไทยชอบขึ้นคีย์ท่อนฮุคสุดท้าย)
- **Mode**: major / natural minor / harmonic minor / modes (dorian, mixolydian) — ใช้เลือก scale สำหรับ Block Mode

### [5] Chord Recognition (ใช้ instrumental ไม่เอาเสียงร้อง)
- โมเดลหลัก BTC (vocabulary ใหญ่: maj, min, 7, maj7, m7, sus, dim, aug)
- ใช้ bass stem หา root → ระบุ slash chord (C/E, D/F#)
- Beat-synchronous smoothing: บังคับเปลี่ยนคอร์ดตรง beat, ลด flicker
- Key-aware prior: คอร์ดที่อยู่ในคีย์ได้คะแนนเพิ่ม แต่ไม่บังคับ (borrowed chord ยังออกได้)
- ผลลัพธ์: list ของ `{start_beat, end_beat, chord, confidence}`

### [6] Vocal f0 Ensemble (บน lead vocal ที่สะอาดแล้ว)
- รัน **RMVPE** (ทนเสียงรบกวน, ออกแบบมาเพื่อเสียงร้อง) hop 10 ms
- รัน **torchcrepe full** (viterbi decoding) hop 10 ms
- (ตัวเลือก) FCPE
- **Fusion**: ต่อ frame เลือก/เฉลี่ยถ่วงน้ำหนักตาม confidence; ถ้าสองโมเดลห่างกัน ~1200 cents (octave error) → ตัดสินด้วยบริบทโน้ตข้างเคียง + harmonic analysis
- Voicing detection: ตัดช่วงหายใจ/เงียบ/เสียงลม (s, sh, ch) ออก
- ผลลัพธ์: เส้น pitch ต่อเนื่อง (Hz + cents) + confidence ต่อ frame → เก็บไว้แสดงเป็นเส้นบน piano roll

### [7] Note Transcription (f0 → โน้ต)
แปลงเส้น pitch ต่อเนื่องให้เป็น "โน้ต" ที่คนอ่านได้ — ขั้นที่ยากที่สุด (รายละเอียดหัวข้อ 7)
- **Note segmentation**: SOME/ROSVOT ให้ boundaries + HMM ของเราเอง (state: silence/attack/stable/transition)
- **Onset hints**: syllable boundaries จาก lyrics alignment [9] + onset จาก spectral flux ของ vocal stem
- **Pitch ของโน้ต**: median ของช่วง "stable" (ตัดช่วง scoop ต้นเสียง และ vibrato ปลายเสียงออกด้วย weighting)
- **Tuning compensation** → **quantize เป็น semitone** → เก็บ `cents_offset` ไว้แสดงด้วย
- **Key-aware decision**: ถ้าโน้ตกำกวม (อยู่กลางระหว่าง 2 semitone, เช่น ±40 cents) ใช้ scale ของคีย์เป็น prior แต่ถ้าชัดเจนว่า chromatic ก็คงไว้ (ไม่ snap แบบมั่ว)
- **Rhythm quantization**: snap เวลาเข้ากับ beat grid (1/16, 1/8T, 1/32 ตามความหนาแน่นโน้ต) โดยเก็บเวลาจริงไว้ด้วย (แสดงได้ทั้ง "ตามจริง" และ "quantized")
- ผลลัพธ์ต่อโน้ต: `pitch (MIDI), name (F#4), start, end, start_beat, duration_beats, cents_offset, confidence, syllable`

### [8] Ornament / Technique Detection
วิเคราะห์รูปร่างเส้น pitch ภายในและระหว่างโน้ต → ติด tag (รายละเอียดหัวข้อ 12)

### [9] Lyrics
- faster-whisper (large-v3, int8_float16) บน lead vocal → ข้อความ + timestamp ระดับคำ
- ภาษาไทย: forced alignment ด้วย wav2vec2 ภาษาไทยผ่าน WhisperX เพื่อ timestamp ละเอียด
- **แนะนำให้มีช่อง "วางเนื้อเพลงเอง"**: เพราะ ASR บนเสียงร้องเพลงพลาดได้ ถ้าวางเนื้อที่ถูกมา ระบบจะทำแค่ forced alignment (แม่นกว่ามาก)
- ตัดคำไทย/แบ่งพยางค์ด้วย PyThaiNLP → map พยางค์ ↔ โน้ต

### [10] Song Model
รวมทุกอย่างเป็น `song.json` (หัวข้อ 19) → Frontend โหลดไปแสดง → Tab Engine ทำงานบน model นี้แบบ real-time

---

## 7. กลยุทธ์ความแม่นยำของโน้ต (หัวใจของโปรเจกต์)

"ตรงที่สุด" ไม่ได้มาจากโมเดลตัวเดียว แต่มาจากหลายชั้นช่วยกัน:

| ปัญหาที่ทำให้โน้ตผิด | วิธีแก้ในระบบ |
|---|---|
| ดนตรี/เสียงประสานรบกวน | RoFormer + karaoke model แยก **lead vocal เท่านั้น** |
| Reverb ทำให้โน้ตลากยาว/ซ้อน | De-reverb model ก่อนวิเคราะห์ |
| Octave error (เพี้ยนไป 1 octave) | Ensemble 2–3 โมเดล + context smoothing + ตรวจ harmonic |
| เพลงจูนไม่ตรง A440 | ตรวจ global tuning offset แล้วชดเชย |
| ลูกคอ/vibrato ทำให้ได้โน้ตยิบย่อย | ตรวจ vibrato แล้วรวมเป็นโน้ตเดียว + tag `~` |
| Scoop ต้นเสียง (ไหลขึ้นจากใต้โน้ต) | ไม่นับช่วง attack ในการหา pitch, แปลงเป็น tag slide-in/bend |
| โน้ตกำกวมระหว่างครึ่งเสียง | Key-aware prior + แสดง confidence ต่ำเป็นสีส้มให้คนตรวจ |
| แบ่งโน้ตผิด (2 โน้ตติดเป็นตัวเดียว) | SOME/ROSVOT + onset จากพยางค์เนื้อร้อง + spectral flux |
| เสียงหายใจ/พยัญชนะถูกนับเป็นโน้ต | voicing threshold + ความยาวขั้นต่ำ + ตรวจ aperiodicity |

**Human-in-the-loop (ส่วนที่ทำให้ "ตรง 100%" ได้จริง)**
- โน้ตทุกตัวมี **confidence** → สีจาง/ขอบส้ม = ควรตรวจ, มีปุ่ม "กระโดดไปโน้ตที่ไม่มั่นใจตัวถัดไป"
- **ฟังเทียบ**: เล่น vocal stem พร้อมเสียง synth ของโน้ตที่แกะได้ (pan ซ้าย/ขวา) → ได้ยินทันทีว่าตัวไหนเพี้ยน
- **Slow-down + Loop** ช่วงที่สงสัย
- แก้ใน piano roll: ลากขึ้นลง (เปลี่ยน pitch), ลากขอบ (ความยาว), แบ่งโน้ต (split), รวมโน้ต (merge)
- ปรับ sensitivity ได้: "ละเอียด (เก็บทุกลูกคอ)" ↔ "เรียบ (เหลือแต่โน้ตหลัก)"

---

## 8. Piano Roll Viewer

```
 ┌────┬───────────────────────────────────────────────────────────────┐
 │ G4 │                         ▓▓▓▓ G4                                │
 │ F#4│               ▓▓▓▓▓▓ F#4      ▓▓ F#4                           │
 │ E4 │ ▓▓▓▓▓ E4  ▓▓ E4  ~~~~~~(เส้น pitch จริง)~~~        ▓▓▓▓▓▓▓ E4   │
 │ D#4│                                                                │
 │ ...│        |playhead                                               │
 ├────┴───────────────────────────────────────────────────────────────┤
 │ Chords:  E           C#m           A            B                   │
 │ Lyrics:  ฉัน  ยัง  รอ  เธอ  อยู่  ตรง  นี้                              │
 │ Beat:    1 . . . 2 . . . 3 . . . 4 . . . | 1 ...                     │
 └────────────────────────────────────────────────────────────────────┘
```

ความสามารถ:
- แกนตั้ง = คีย์เปียโน (คลิกที่คีย์เพื่อฟังเสียงโน้ตนั้น), **ไฮไลต์แถวโน้ตที่อยู่ในคีย์** ของเพลง
- แกนนอน = เวลา พร้อม grid bar/beat จาก tempo map จริง
- แท่งโน้ตแสดงชื่อเต็ม **พร้อม octave** แบบ Scientific Pitch Notation (C4 = Middle C) เช่น `F#4`, ตัวเลือก: ชื่อแบบ solfège (โด เร มี), ตัวเลข scale degree (1 2 3), หรือ ♯/♭ ตามคีย์ (เช่นคีย์ F ใช้ B♭ ไม่ใช้ A#)
- Hover โน้ต → tooltip: ชื่อ, MIDI number, ความถี่ Hz, cents offset, ความยาว (beats), confidence, พยางค์
- ซ้อน **เส้น pitch จริง** ของเสียงร้อง (เห็นลูกคอ/vibrato ชัด)
- **Scroll mode**: โน้ตวิ่งเข้าหา playhead (แบบเกม) หรือ playhead วิ่งผ่านหน้า
- Zoom แนวนอน/แนวตั้ง, follow playhead, mini-map ทั้งเพลง
- **ตัวเลือกแสดง octave สำหรับกีตาร์**: กีตาร์เป็นเครื่องดนตรี "transposing" (โน้ตที่เขียนสูงกว่าเสียงจริง 1 octave) → มี toggle "Concert pitch / Guitar written pitch" เพื่อไม่สับสน
- Ghost note ของ backing vocal (เลือกแสดงได้) เผื่ออยากแกะไลน์ประสาน

---

## 9. Chord Sheet + เนื้อร้อง + Metronome

### 9.1 Chord Sheet (แบบเว็บแจกคอร์ด)
```
[Verse 1]
E                    C#m
ฉันยังรอเธออยู่ตรงนี้      ไม่เคยไปไหน
A                    B
แม้วันเวลาจะผ่านไป      ...
```
- คอร์ดวางตรงพยางค์ที่มันเริ่มพอดี (จาก timestamp)
- จัดบรรทัดตามท่อนเพลง (section) และวลี (phrase จากช่วงหยุดหายใจ)
- Transpose ได้ (ปุ่ม −/+) และ capo (แสดงทรงคอร์ดหลังติด capo)
- แสดง chord diagram เมื่อ hover/คลิก, มีทรงคอร์ดหลายแบบ (open / barre)
- Auto-scroll ตามเพลง, ไฮไลต์คำที่กำลังร้อง (karaoke style)
- Export เป็น PNG/PDF/TXT ได้
- โหมด "ซ่อนคอร์ดซ้ำ" / "แสดงทุก bar"

### 9.2 Metronome ตรงจังหวะเพลง
- ✅ Checkbox เปิด/ปิด
- คลิกเกิดตาม **beat grid จริง** จาก Beat This! (ไม่ใช่ BPM คงที่) → ตามเพลงที่ tempo แกว่งได้
- เสียงต่างกัน: downbeat (เน้น) / beat / subdivision (ตัวเลือก 8th, 16th, triplet)
- ปรับ volume, เลือกเสียง (click, woodblock, hi-hat), offset เวลา (ชดเชย latency ของหูฟัง bluetooth)
- **Count-in** 1–2 ห้องก่อนเริ่มเล่นใน loop
- ตอน slow-down metronome ช้าตามเป็นสัดส่วน
- โหมด "Metronome only" (ปิดเพลง เหลือเคาะ) สำหรับซ้อมเอง
- เทคนิค: schedule ล่วงหน้าด้วย Web Audio clock (lookahead ~100 ms) → แม่นระดับ sample ไม่ jitter

---

## 10. Auto Guitar Tab Engine (Fingering Optimizer)

### 10.1 แนวคิด
โน้ต 1 ตัวเล่นได้หลายตำแหน่งบนคอ (เช่น E4 = สาย 1 ช่อง 0, สาย 2 ช่อง 5, สาย 3 ช่อง 9, สาย 4 ช่อง 14) → ต้องเลือก "ลำดับตำแหน่ง" ทั้งเพลงที่เล่นง่ายที่สุด
→ เป็นปัญหา **shortest path** แก้ด้วย **Dynamic Programming / Viterbi** (เร็ว, ได้คำตอบดีที่สุดตาม cost)

### 10.2 ขั้นตอน
1. **Transpose** ตามคีย์ที่เลือก + capo + tuning (Standard, Drop D, Eb, ...)
2. **Octave fitting**: ถ้าเสียงร้องอยู่ช่วงที่เล่นยาก ระบบแนะนำ octave shift ทั้งเพลง (หรือทีละวลี)
3. **Candidate generation**: ทุกโน้ต → list ตำแหน่ง (string, fret) ที่เป็นไปได้ (0–22/24 fret)
4. **Constraint filter**: Block Mode (หัวข้อ 11), จำกัด fret สูงสุด, ห้าม/อนุญาตสายเปล่า
5. **Viterbi** หาเส้นทาง cost ต่ำสุด
6. **Technique pass**: ใส่ slide/hammer/pull/bend ที่สอดคล้องกับตำแหน่งที่เลือก
7. **Playability report**: คะแนนความยาก ต่อโน้ต/ห้อง/ท่อน

### 10.3 Cost Function (ปรับน้ำหนักได้ใน Settings / Preset)
| ปัจจัย | ความหมาย |
|---|---|
| `shift_cost` | ระยะย้ายตำแหน่งมือ (หน่วย fret) × น้ำหนัก — **ยิ่งโน้ตถี่ (เวลาห่างน้อย) ยิ่งแพง** |
| `stretch_cost` | ความกว้างนิ้วในตำแหน่งเดียว (>4 ช่อง = แพงมาก, >5–6 = ห้าม) |
| `string_skip_cost` | กระโดดข้ามสาย (เช่นสาย 1 → สาย 4) |
| `fret_height_cost` | ช่องสูงมาก (เกิน 15) แพงขึ้นเล็กน้อย |
| `open_string_pref` | ชอบ/ไม่ชอบสายเปล่า (สายเปล่า sustain ต่างและคุม vibrato ไม่ได้) |
| `same_string_legato_bonus` | ถ้าเสียงร้องเป็น legato/slide → ให้รางวัลถ้าอยู่สายเดียวกัน (จะได้ slide/hammer ได้) |
| `bend_feasibility` | โน้ตที่ต้อง bend ห้ามอยู่บนสายเปล่า, bend เกิน 1.5 เสียงบนสายพันแพงมาก |
| `vibrato_feasibility` | โน้ตที่มี vibrato ไม่ควรเป็นสายเปล่า |
| `position_consistency` | ชอบอยู่ในตำแหน่งเดิมทั้งวลี (phrase) |
| `timbre_pref` | ตัวเลือก: "หวาน/หนา" (ชอบสายต่ำช่องสูง) vs "สว่าง" (ชอบสายสูง) |

### 10.4 ประมวลผลความเป็นไปได้ของการเล่น (Playability Analyzer)
- เช็กทุกการเปลี่ยนโน้ต: **ระยะทาง (fret) ÷ เวลาที่มี (ms)** → ถ้าเกินเกณฑ์ = "เปลี่ยนตำแหน่งไม่ทัน"
- เมื่อเจอจุดเล่นยาก ระบบหาทางเลือกให้อัตโนมัติ **โดยโน้ตยังถูกต้องเหมือนเดิม**:
  1. ย้ายไปสาย/ช่องอื่นที่ pitch เท่ากัน
  2. ใช้ **slide** เป็นตัวเปลี่ยนตำแหน่ง (เสียงลื่น เหมือนเสียงร้อง)
  3. ใช้สายเปล่าเป็นตัวคั่นเพื่อมีเวลาย้ายมือ
  4. (ถ้ายังไม่ได้ และผู้ใช้อนุญาต) เสนอ octave shift เฉพาะวลี — ต้องกดยืนยันเพราะเปลี่ยนเสียง
- **Heatmap ความยาก** บนแทป: เขียว/เหลือง/แดง
- **Difficulty score** ต่อท่อน (1–10) และทั้งเพลง
- คลิกจุดแดง → ดู **Top-3 fingering ทางเลือก** พร้อมแสดงบน fretboard แล้วเลือกได้
- แนะนำ **นิ้วที่ใช้** (1–4) ใต้แทป (ตัวเลือก)

---

## 11. Block Mode (จำกัดโซนบนคอกีตาร์)

### 11.1 แนวคิด
ผู้ใช้อยากเล่นในโซนเดียว (เช่น "Box 1 ของ E minor pentatonic ช่อง 12–15") → แทปต้องอยู่แค่ในนั้น แต่ **กระจายใช้ทุกสาย** ไม่ใช่กองอยู่สายเดียว

### 11.2 การสร้าง Block อัตโนมัติจาก Key
เมื่อรู้คีย์ ระบบสร้าง block ให้เลือก หลายระบบ:
| ระบบ | จำนวน block | เหมาะกับ |
|---|---|---|
| **CAGED** | 5 shape | คนที่คิดเป็นทรงคอร์ด |
| **3 Notes Per String (3NPS)** | 7 position | เล่นเร็ว legato |
| **Pentatonic Box** | 5 box | โซโล่/เมโลดี้ง่ายๆ |
| **Custom** | ลากเลือกช่วงบน fretboard เอง | อิสระ |

แต่ละ block เก็บ: `fret_min, fret_max, allowed_positions[(string,fret)], scale, label`
ตัวอย่าง: คีย์ G major → Block "CAGED E-shape @ 3" = ช่อง 2–6 ทุกสาย

### 11.3 UI
```
 Fretboard (แสดงทั้งคอ 0–22)
 ═══╦═══╦═══╦═══╦═══╦═══╦═══╦═══╦═══╦═══╦═══╦═══╦═══
    ║ ● ║   ║[█ █ █ █]║   ║ ● ║   ║[▒ ▒ ▒ ▒ ▒]║   ...
 ───────────────────────────────────────────────────
  [Block 1] [Block 2 ✓] [Block 3] [Block 4 ✓] [Block 5]  [+ Custom]
  โหมด:  ◉ เล่นแค่ block เดียว  ○ ย้ายระหว่าง block ที่เลือกได้ (ตามวลี)
  นอก block:  ◉ ย้าย octave อัตโนมัติ  ○ ยืด 1 ช่อง  ○ แจ้งเตือนสีแดง
  [ 🎸 สร้างแทปกีต้า ]
```
- เลือกได้หลาย block (multi-select) → อนุญาตเปลี่ยน block เฉพาะ **ตอนต้นวลี/จุดหายใจ** หรือผ่าน slide
- เลือก block ต่างกันต่อท่อนได้ (Verse ใช้ block 1, Chorus ใช้ block 4)
- แสดง preview: จุดทุกโน้ตของเพลงบน fretboard ว่าตกใน block กี่ % ก่อนกดสร้าง

### 11.4 การทำงานใน Engine
- Candidate filter: ตัดทุกตำแหน่งที่อยู่นอก block ออก
- เพิ่ม **`string_spread_bonus`**: ให้รางวัลเมื่อใช้ตำแหน่งที่ทำให้มือไม่ต้องขยับ (ซึ่งโดยธรรมชาติจะกระจายข้ามสาย) และลงโทษการยืดบนสายเดียว
- โน้ตที่ไม่มีตำแหน่งใน block เลย (range เกิน) → จัดการตามตัวเลือกที่ผู้ใช้ตั้ง (ย้าย octave / ยืด / แจ้งเตือน) และ **แจ้งชัดเจนทุกครั้ง** ว่าโน้ตตัวไหนถูกเปลี่ยน

---

## 12. แปลงลูกเล่นเสียงร้อง → เทคนิคกีตาร์

วิเคราะห์จากเส้น f0 (ความละเอียด 10 ms) ระหว่างและภายในโน้ต:

| ลูกเล่นเสียงร้อง | ลักษณะบนเส้น pitch | เทคนิคกีตาร์ | สัญลักษณ์แทป |
|---|---|---|---|
| Vibrato | แกว่งเป็นคาบ 4.5–7 Hz, กว้าง > ~25 cents | Vibrato (กว้าง/แคบตาม extent) | `~` / `~~` |
| Scoop ขึ้น (ไหลจากใต้เข้าโน้ต) | pitch เริ่มต่ำกว่าแล้วไหลขึ้นภายใน ~50–150 ms | Bend ขึ้น (pre-bend ไม่ได้) หรือ slide in | `7b9` / `/9` |
| Fall-off (ปลายเสียงตก) | pitch ตกท้ายโน้ต | Slide out ลง / release | `9\` |
| Portamento/ไหลระหว่างโน้ตต่อเนื่อง | pitch ต่อเนื่องไม่มี onset ใหม่, เปลี่ยน > 2 semitone | Slide (legato slide) | `5/9` |
| ไหลระหว่างโน้ตใกล้ (1–2 semitone) ขึ้น | ต่อเนื่อง ไม่มี onset | Bend หรือ Hammer-on (เลือกตามความเร็ว) | `5b7` / `5h7` |
| โน้ตขึ้นเร็วไม่มี onset ใหม่ (melisma) | step ขึ้นรวดเร็ว | Hammer-on | `5h7` |
| โน้ตลงเร็วไม่มี onset ใหม่ | step ลงรวดเร็ว | Pull-off | `7p5` |
| ลูกคอขึ้น-ลง (turn/run) | หลายโน้ตเร็วติดกัน | hammer/pull ต่อเนื่อง (trill/run) | `5h7p5` |
| Grace note | โน้ตสั้นมาก < ~80 ms ก่อนโน้ตหลัก | Grace note / quick slide | `(5)7` |
| Bend แล้วปล่อย | ขึ้นแล้วลงกลับ | Bend & Release | `7b9r7` |
| เสียงลากยาว | stable | Let ring / sustain | `—` |

**กติกาเลือกเทคนิค (ร่วมกับ Tab Engine)**
- Bend ใช้ได้เมื่อ: ไม่ใช่สายเปล่า, ระยะ ≤ 2 semitone (ตั้งได้), ไม่อยู่บนสายพันเกิน 1 เสียง (เตือน)
- Slide ต้องอยู่สายเดียวกัน → engine ให้รางวัลตำแหน่งที่ทำ slide ได้เมื่อเสียงร้องไหล
- Hammer/Pull ต้องสายเดียวกันและระยะไม่เกินการยืดนิ้ว
- ผู้ใช้เลือก **ระดับลูกเล่น**: Off / Basic (slide+vibrato) / Full (ทุกอย่าง) / "Vocal-like" (ใช้ bend+slide หนักให้เหมือนคนร้องที่สุด)
- ทุกเทคนิคที่ระบบใส่ แก้/ลบได้ใน Tab Editor

---

## 13. แนะนำคีย์ที่เล่นง่าย + Capo

- ทดลอง transpose ทุกคีย์ −6 ถึง +6 semitone (12 แบบ) × ตัวเลือก capo 0–7
- รัน Tab Engine แบบเร็ว (ไม่ต้องแสดงผล) ทุกแบบ → ได้คะแนน (เร็วมากเพราะ Numba, < 1 วินาทีรวม)
- คะแนนจาก: fingering cost รวม, จำนวนจุดแดง, range ที่ใช้, ความเป็นมิตรของคีย์กับกีตาร์ (E, A, D, G, Em, Am มีสายเปล่าช่วย), ความง่ายของคอร์ด (ถ้าจะเล่นคอร์ดด้วย)
- แสดงเป็นตาราง:

| อันดับ | คีย์ | Capo | ความยากเมโลดี้ | ความยากคอร์ด | หมายเหตุ |
|---|---|---|---|---|---|
| ⭐ 1 | E (ต้นฉบับ) | 0 | 3/10 | 2/10 | สายเปล่า E/B ช่วยได้มาก |
| 2 | D | 2 (เสียงเท่าต้นฉบับ) | 3/10 | 2/10 | ทรงคอร์ด D ง่าย |
| 3 | G | 0 | 4/10 | 2/10 | เสียงเปลี่ยนจากต้นฉบับ |

- แยกชัดเจน 2 แบบ: **"เสียงเท่าต้นฉบับ (ใช้ capo)"** vs **"เปลี่ยนคีย์ (เสียงต่างจากต้นฉบับ)"**
- ตัวเลือก tuning: Standard / Eb standard (เพลงร็อคไทยหลายเพลงจูนครึ่งเสียงต่ำ) / Drop D

---

## 14. Tab Editor (จิ้มแก้ได้ทุกตัว)

### 14.1 หลักการสำคัญ
ข้อมูลแทปเก็บเป็น **event ที่มีตำแหน่งเวลา (beat position) ของตัวเอง** ไม่ใช่ข้อความเรียงต่อกัน → แก้/ลบตัวไหน **ไม่กระทบตัวอื่น** ไม่ต้องลบไล่ตัวหลังเหมือนพิมพ์ text tab

### 14.2 การโต้ตอบ
| การกระทำ | ผล |
|---|---|
| คลิกตัวเลขในแทป | เลือกโน้ตนั้น + ฟังเสียง + ไฮไลต์บน piano roll/fretboard/เนื้อร้อง (sync กันทุก view) |
| พิมพ์ตัวเลข (0–24) | เปลี่ยนช่อง (pitch เปลี่ยนตาม) |
| ↑ / ↓ | ย้ายสาย **โดยรักษา pitch เดิม** (คำนวณช่องให้อัตโนมัติ) |
| Alt + ↑ / ↓ | เปลี่ยน pitch ทีละครึ่งเสียง (สายเดิม) |
| ← / → | เลื่อนไปโน้ตก่อน/ถัดไป |
| Shift + ← / → | เลื่อนเวลาโน้ตตาม grid |
| `H` / `P` / `S` / `B` / `R` / `V` / `G` | Hammer / Pull / Slide / Bend / Release / Vibrato / Grace — กดซ้ำ = ถอด |
| `Delete` | ลบโน้ต → กลายเป็นตัวหยุด (ตัวอื่นอยู่ที่เดิม) |
| `Ctrl+Delete` | ลบแล้วดึงตัวหลังมาแทน (ripple) — ตัวเลือก |
| ดับเบิลคลิกที่ว่าง | เพิ่มโน้ตใหม่ตรงนั้น |
| คลิกขวา | Context menu: เปลี่ยนความยาว, ใส่เทคนิค, ดูตำแหน่งทางเลือก, split, merge, lock |
| ลากเลือกหลายตัว | แก้พร้อมกัน (ย้ายสาย, transpose, ใส่เทคนิค, ย้ายเข้า block อื่น) |
| `Ctrl+Z` / `Ctrl+Y` | Undo / Redo ไม่จำกัด (Immer patches) |
| `L` | **Lock** โน้ต → ถ้ากด regenerate แทปทั้งเพลง ตัวที่ lock จะไม่ถูกเปลี่ยน และ engine จะจัดตัวรอบข้างให้เข้ากับมัน |

### 14.3 Popover แก้ละเอียด (เมื่อคลิกโน้ต)
```
┌─ โน้ต: F#4 (สาย 2, ช่อง 7) ─────────────┐
│ สาย: [1][2●][3][4][5][6]  ช่อง: [ 7 ]   │
│ ความยาว: [♩.] [♪] [♬]  เวลา: bar 12.3   │
│ เทคนิคเข้า:  ○none ○slide in ○grace      │
│ เทคนิค:  ☐Bend[½ 1 1½] ☐Vibrato ☐Let ring│
│ เทคนิคไปตัวถัดไป: ○none ○H ○P ○slide     │
│ ตำแหน่งทางเลือก: (3,11) (4,16)           │
│ [🔒 Lock] [🗑 ลบ] [🔊 ฟัง]                │
└────────────────────────────────────────┘
```

### 14.4 ทุก view sync กัน
แก้ในแทป ↔ piano roll ↔ fretboard ↔ chord sheet อัปเดตทันที (single source of truth ใน store)

### 14.5 Playback แทป
- เล่นเสียงกีตาร์สังเคราะห์ (soundfont guitar) ของแทปที่แก้แล้ว ซ้อนกับเพลงจริง เพื่อตรวจ
- Playhead วิ่งบนแทป, auto-scroll, loop ช่วงที่เลือก

---

## 15. Export ทีละท่อนเป็นรูป (และฟอร์แมตอื่น)

### 15.1 Export รูป
- เลือกท่อน (ติ๊กหลายท่อนได้ หรือ "ทุกท่อน") → ได้ไฟล์แยกต่อท่อน เช่น `ชื่อเพลง_02_Chorus.png`
- หรือเลือกช่วงเอง (ลากบน timeline)
- **Layout ต่อรูป** (เลือกได้):
  - Header: ชื่อเพลง, ศิลปิน, ชื่อท่อน, Key, Capo, Tuning, BPM, Time sig
  - แถว: คอร์ด / แทป / (ตัวเลือก) โน้ตสากล / ชื่อโน้ต / เนื้อร้อง / นิ้วที่ใช้
  - Footer: legend สัญลักษณ์เทคนิค, ลายน้ำ/ชื่อเพจ (ตัวเลือก)
- **Preset ขนาด**: 1920×1080 (YouTube/จอ), 1080×1350 (IG portrait), 1080×1920 (Story/TikTok), A4 (พิมพ์)
- **Theme**: สว่าง / มืด / โปร่งใส (PNG alpha) / ฟอนต์ไทยเลือกได้
- ความละเอียด: 1x / 2x / 3x (render จาก SVG จึงคมเสมอ)
- ไฟล์: PNG, SVG, PDF (รวมทุกท่อนเป็นเล่มเดียวได้)
- Batch export + เปิดโฟลเดอร์ผลลัพธ์อัตโนมัติ

### 15.2 Export อื่น
| ฟอร์แมต | ใช้ทำอะไร |
|---|---|
| MIDI (.mid) | เมโลดี้/คอร์ด ไปใช้ใน DAW |
| Guitar Pro (.gp) | เปิดใน Guitar Pro / TuxGuitar / Songsterr-style |
| MusicXML | MuseScore / โปรแกรมโน้ตสากล |
| Text tab (.txt) | โพสต์ในเว็บ/โซเชียล |
| Chord sheet (.txt/.pdf) | แจกคอร์ด |
| Stems (.wav/.flac) | vocal / backing (ไม่มีร้อง) ไว้เล่นทับ |
| LRC | เนื้อร้องพร้อมเวลา |

---

## 16. บันทึกโปรเจกต์ + Cache

### 16.1 โปรเจกต์
```
Projects/
└── 2026-10-03_ชื่อเพลง/
    ├── project.json         # metadata + การตั้งค่า + version
    ├── song.json            # Song Model (notes, chords, beats, sections, lyrics)
    ├── tab.json             # แทปปัจจุบัน + การตั้งค่า block/คีย์/capo
    ├── history/             # snapshot เวอร์ชัน (autosave ทุก 2 นาที, เก็บ 20 ล่าสุด)
    ├── audio/
    │   ├── source.flac
    │   └── stems/ lead_vocal.flac, backing_vocal.flac, instrumental.flac, bass.flac, drums.flac
    ├── analysis/ f0.npz, chroma.npz ...
    └── exports/
```
- **Library หน้าแรก**: รายการโปรเจกต์ (ภาพปก YouTube, ชื่อ, key, BPM, แก้ล่าสุด) ค้นหา/กรองได้ (SQLite index)
- Autosave + "กลับไปเวอร์ชันก่อน"
- Export/Import โปรเจกต์เป็นไฟล์เดียว `.melotab` (zip) เพื่อย้ายเครื่อง/แชร์

### 16.2 Cache (ไม่ต้องประมวลผลซ้ำ)
- Cache key ต่อขั้น = `hash(audio) + ชื่อขั้น + เวอร์ชันโมเดล + พารามิเตอร์`
- ถ้าเปลี่ยนแค่ "sensitivity การแบ่งโน้ต" → รันใหม่แค่ขั้น [7] เป็นต้นไป (stems, f0 ใช้ของเดิม)
- ลิงก์ YouTube เดิม → รู้จาก video ID ทันที ไม่ดาวน์โหลดซ้ำ
- Global cache folder แยกจากโปรเจกต์ (ตั้งขนาดสูงสุด เช่น 30 GB, ล้างแบบ LRU, ปุ่ม "ล้าง cache")
- โมเดล AI โหลดครั้งแรกแล้วเก็บไว้ใน `models/` (ไม่ดาวน์โหลดซ้ำ) + หน้า Model Manager (ดูขนาด/เวอร์ชัน/อัปเดต)
- RAM cache: เพลงที่เปิดอยู่เก็บ waveform/peaks/spectrogram ใน RAM (มี 32 GB เหลือเฟือ)

---

## 17. Status / System Monitor

### 17.1 Status Bar (ล่างจอ ตลอดเวลา)
```
● กำลังวิเคราะห์: [2/9] แยกเสียงร้อง (Mel-Band RoFormer) ███████░░░ 68%  ETA 0:24  [ยกเลิก]
GPU 97% ▮▮▮▮▮▮▮▮▮▯  VRAM 5.8/8.0 GB  │ CPU 41%  │ RAM 9.2/32 GB  │ GPU 71°C  │ ✓ CUDA
```

### 17.2 Job Panel (กดขยายจาก status bar)
```
Analyze: "ชื่อเพลง"                            เวลาที่ใช้ 1:12
 ✅ 0. ดาวน์โหลด YouTube              12.4s
 ✅ 1. เตรียมไฟล์เสียง                  1.1s
 🔄 2. แยกเสียงร้อง        ██████░░░ 68%   (chunk 17/25)
 🔄 3. จังหวะ/ท่อนเพลง     ████░░░░░ 45%   (รันขนานบน CPU)
 ⏳ 4. Key + Tuning
 ⏳ 5. คอร์ด
 ⏳ 6. Pitch เสียงร้อง
 ⏳ 7. แกะโน้ต
 ⏳ 8. ลูกเล่น/เทคนิค
 ⏳ 9. เนื้อร้อง
 [📜 Log]  [⏸ พัก]  [✖ ยกเลิก]
```
- Progress รวม = ถ่วงน้ำหนักตามเวลาเฉลี่ยของแต่ละขั้น (เรียนรู้จากการรันจริงบนเครื่องนี้ → ETA แม่นขึ้นเรื่อยๆ)
- **Heartbeat**: backend ส่งสัญญาณทุก 1 วินาที — ถ้าขาด > 10 วินาที UI แสดง "backend ไม่ตอบสนอง" + ปุ่ม restart → รู้ทันทีว่าค้างจริงหรือแค่ช้า
- ผลลัพธ์แสดงทีละส่วนทันทีที่เสร็จ (เช่น beat/key เสร็จก่อน → เปิดดูได้เลยระหว่างรอโน้ต)
- แจ้งเตือน Windows (toast) เมื่องานเสร็จ
- Error ที่อ่านรู้เรื่อง เช่น "VRAM ไม่พอ → ระบบลด chunk size แล้วลองใหม่อัตโนมัติ"

### 17.3 System Monitor (หน้าเต็ม)
- กราฟ real-time 60 วินาที: GPU util, VRAM, GPU temp/power, CPU ต่อ core (P-core/E-core), RAM
- โมเดลที่โหลดอยู่ใน VRAM ตอนนี้ + ปุ่ม "ปลดโมเดลทั้งหมด"
- แหล่งข้อมูล: `pynvml` (GPU), `psutil` (CPU/RAM) → WebSocket ทุก 1 วินาที

---

## 18. การรีดประสิทธิภาพ (i5-13500HX / RTX 4060 Laptop 8GB / RAM 32GB)

### 18.1 ข้อมูลเครื่อง
- **CPU**: 14 cores (6 P-core + 8 E-core), 20 threads
- **GPU**: RTX 4060 Laptop, 8 GB VRAM, สถาปัตยกรรม Ada (รองรับ FP16/BF16 Tensor Core ดี)
- **RAM**: 32 GB

### 18.2 กลยุทธ์ GPU (8 GB = ต้องบริหาร VRAM)
- **GPU Worker process เดียว** ถือ GPU, รันโมเดล **ทีละตัว** → โหลด → ประมวลผล → ปลด (`del model; torch.cuda.empty_cache()`)
- **Mixed precision**: `torch.autocast("cuda", dtype=torch.bfloat16)` (หรือ fp16) → เร็วขึ้น ~1.5–2x ใช้ VRAM ครึ่งเดียว
- **Chunking + overlap** สำหรับ separation; ปรับ batch/chunk อัตโนมัติตาม VRAM ว่าง (catch OOM → ลดแล้ว retry)
- `torch.backends.cudnn.benchmark = True`, `torch.inference_mode()`
- faster-whisper ใช้ `compute_type="int8_float16"` (large-v3 ใช้ VRAM ราว 3–4 GB)
- (Phase หลัง) export RMVPE/CREPE เป็น ONNX → TensorRT FP16 เพื่อเร็วขึ้นอีก
- `torch.compile` สำหรับโมเดลที่ใช้บ่อย (ทดสอบก่อน บน Windows อาจต้องใช้ WSL2)

**VRAM Budget (ประมาณการ — ต้องวัดจริง)**
| ขั้น | โมเดล | VRAM โดยประมาณ |
|---|---|---|
| Separation | Mel-Band RoFormer (bf16, chunk 8s) | 3–6 GB |
| Karaoke / De-reverb | RoFormer/MDX | 2–4 GB |
| f0 | RMVPE + torchcrepe | 1–2 GB |
| Notes | SOME | ~1 GB |
| Lyrics | faster-whisper large-v3 int8 | 3–4 GB |
| Beat | Beat This! | < 1 GB |

### 18.3 กลยุทธ์ CPU (ใช้ทุก core ขณะ GPU ทำงาน)
- **ProcessPoolExecutor** (ไม่ใช่ thread เพราะ GIL) สำหรับ: Beat This!/allin1 (เวอร์ชัน CPU ได้ถ้า GPU ไม่ว่าง), essentia key, chord post-processing, ffmpeg, การทำ waveform peaks
- Pipeline overlap: ระหว่าง GPU แยกเสียง → CPU ทำ rhythm + key บน mix ไปพร้อมกัน
- Tab Engine เขียนด้วย **Numba** (`@njit(parallel=True)`) → Viterbi ทั้งเพลง < 50 ms, Easy-key search 12×8 แบบ ขนานทุก core
- ตั้ง thread ของ numpy/torch CPU ให้ไม่แย่งกัน (`OMP_NUM_THREADS` ต่อ worker)

### 18.4 RAM 32 GB
- Preload stems ของโปรเจกต์ที่เปิดใน RAM, decode audio ครั้งเดียว
- เก็บ spectrogram/peaks หลายระดับ zoom ใน RAM → ซูม/เลื่อน piano roll ลื่น
- Frontend: ส่ง audio ให้ Web Audio เป็น ArrayBuffer ครั้งเดียว

### 18.5 Notebook-specific
- แนะนำเสียบปลั๊ก + โหมด Performance (Armoury Crate/Vantage แล้วแต่ยี่ห้อ) + NVIDIA Control Panel → ให้ python ใช้ High-performance GPU
- Monitor อุณหภูมิ — ถ้า GPU > 85°C แสดงเตือนใน status bar
- Driver NVIDIA + CUDA 12.x ล่าสุด, ติดตั้ง PyTorch ที่ตรง CUDA

---

## 19. Data Model (song.json / tab.json แบบย่อ)

```jsonc
// song.json
{
  "version": 1,
  "source": { "type": "youtube", "id": "xxxx", "title": "...", "artist": "...", "duration": 241.3, "audio_hash": "sha256..." },
  "tuning_offset_cents": -12,
  "key": { "tonic": "E", "mode": "major", "confidence": 0.87, "alternatives": [{"tonic":"C#","mode":"minor","confidence":0.71}] },
  "key_changes": [ { "time": 182.4, "tonic": "F", "mode": "major" } ],
  "tempo": { "bpm_mean": 76.2, "map": [ { "time": 0.0, "bpm": 76.0 } ] },
  "time_signatures": [ { "bar": 1, "num": 4, "den": 4 } ],
  "beats": [ { "time": 0.52, "bar": 1, "beat": 1 } ],
  "sections": [ { "id": "s2", "label": "Chorus", "start_bar": 17, "end_bar": 25 } ],
  "chords": [ { "start_beat": 0, "end_beat": 4, "symbol": "E", "bass": null, "confidence": 0.92 } ],
  "lyrics": [ { "text": "ฉัน", "start": 12.31, "end": 12.58, "note_ids": ["n1"] } ],
  "notes": [
    {
      "id": "n1", "midi": 64, "name": "E4", "freq": 329.6,
      "start": 12.31, "end": 12.58, "start_beat": 24.0, "dur_beats": 0.5,
      "cents_offset": -8, "confidence": 0.94,
      "ornaments": [ { "type": "scoop_in", "from_cents": -150, "dur_ms": 90 } ],
      "edited": false
    }
  ],
  "f0_ref": "analysis/f0.npz"
}
```

```jsonc
// tab.json
{
  "settings": { "transpose": 0, "capo": 0, "tuning": ["E2","A2","D3","G3","B3","E4"],
                "blocks": ["caged_E@0"], "block_mode": "single", "out_of_block": "octave_shift",
                "technique_level": "full", "cost_preset": "melodic_vocal_like" },
  "events": [
    { "id": "t1", "note_id": "n1", "string": 1, "fret": 0, "start_beat": 24.0, "dur_beats": 0.5,
      "techniques": { "in": "slide_in", "on": ["vibrato"], "to_next": "hammer" },
      "bend": null, "finger": 1, "locked": false, "difficulty": 0.2 }
  ]
}
```
- `tab.event.note_id` ผูกกับโน้ตใน song → แก้ pitch ฝั่งไหนก็ sync
- `start_beat` ทำให้แก้รายตัวได้อิสระ (ไม่ใช่ข้อความเรียงต่อ)

---

## 20. API (Backend ↔ Frontend)

| Method | Endpoint | หน้าที่ |
|---|---|---|
| POST | `/projects` | สร้างโปรเจกต์จาก URL หรือไฟล์ |
| GET | `/projects` / `/projects/{id}` | รายการ / โหลดโปรเจกต์ |
| POST | `/projects/{id}/analyze` | เริ่ม pipeline (เลือกขั้น/พารามิเตอร์ได้) → คืน `job_id` |
| POST | `/jobs/{id}/cancel` | ยกเลิกงาน |
| POST | `/projects/{id}/retranscribe` | แกะโน้ตใหม่ด้วย sensitivity ใหม่ (ใช้ cache) |
| POST | `/projects/{id}/tab/generate` | สร้างแทป (settings: key, capo, blocks, technique level, locked notes) |
| POST | `/projects/{id}/tab/alternatives` | ขอ fingering ทางเลือกของช่วง/โน้ต |
| GET | `/projects/{id}/keys/suggest` | แนะนำคีย์ง่าย + capo |
| PUT | `/projects/{id}/song` / `/tab` | บันทึกการแก้ไข |
| POST | `/projects/{id}/export` | export (png/svg/pdf/gp/midi/musicxml/txt, sections) |
| GET | `/audio/{project}/{stem}` | stream ไฟล์เสียง/stem |
| WS | `/ws` | events: `job.progress`, `job.stage`, `job.done`, `job.error`, `system.stats`, `heartbeat`, `partial.result` |

ตัวอย่าง WebSocket message:
```json
{ "type": "job.progress", "job_id": "j42", "stage": "separation", "stage_index": 2, "stage_total": 9,
  "stage_pct": 68.0, "overall_pct": 31.5, "eta_s": 24, "detail": "chunk 17/25" }
```

> หมายเหตุการออกแบบ: Tab Engine อาจคอมไพล์เป็น WASM ไว้ฝั่ง frontend ด้วยในอนาคต เพื่อให้การเปลี่ยน block/ลากแก้ regenerate ได้ทันทีโดยไม่ต้องวิ่งผ่าน backend

---

## 21. โครงสร้างโฟลเดอร์ซอร์สโค้ด

```
melotab/
├── apps/
│   ├── desktop/                  # Tauri 2 (Rust shell, sidecar config)
│   └── web/                      # React + TS + Vite
│       └── src/
│           ├── features/
│           │   ├── library/        # หน้ารวมโปรเจกต์
│           │   ├── import/         # วางลิงก์/ลากไฟล์
│           │   ├── pianoroll/      # PixiJS piano roll
│           │   ├── chordsheet/
│           │   ├── tab/            # renderer + editor + popover
│           │   ├── fretboard/      # block selector
│           │   ├── keysuggest/
│           │   ├── export/
│           │   └── status/         # status bar, job panel, system monitor
│           ├── audio/              # transport, metronome scheduler, stretch, synth
│           ├── store/              # zustand + undo/redo
│           ├── api/                # REST + WS client
│           └── theory/             # ชื่อโน้ต, scale, chord, transpose (shared logic)
├── backend/
│   ├── melotab/
│   │   ├── api/                  # FastAPI routes + ws
│   │   ├── jobs/                 # orchestrator, DAG, gpu_worker, cpu_pool
│   │   ├── pipeline/
│   │   │   ├── ingest.py  prep.py  separation.py  rhythm.py  tonal.py
│   │   │   ├── chords.py  f0.py  notes.py  ornaments.py  lyrics.py
│   │   ├── tab/                  # candidates, cost, viterbi (numba), blocks, techniques, keysuggest
│   │   ├── export/               # svg layout, png, pdf, midi, musicxml, gp
│   │   ├── store/                # project io, sqlite, cache
│   │   ├── monitor/              # pynvml, psutil
│   │   └── models/               # plugin wrappers ของแต่ละโมเดล (สลับได้)
│   ├── tests/
│   └── eval/                     # สคริปต์วัดความแม่น (mir_eval)
├── models/                       # น้ำหนักโมเดล (gitignore)
├── docs/plan.md
└── scripts/                      # setup, download models, benchmark
```

---

## 22. ฟีเจอร์เสริมที่แนะนำเพิ่ม (ตอบคำถาม "เพิ่มไรอีกดีมั้ย")

**เรียงตามความคุ้มค่าสำหรับมือกีตาร์สายเมโลดี้**

1. **Slow-down + Loop A-B** (เสียงไม่เพี้ยน) — แทบจำเป็นสำหรับการซ้อมและตรวจโน้ต ⭐⭐⭐
2. **Stem Mixer** — ปรับ volume/mute/solo: ร้อง, ดนตรี, เบส, กลอง → ได้ **backing track ไม่มีเสียงร้อง** ไว้เล่นกีตาร์ทับแทนนักร้อง ⭐⭐⭐
3. **Synth Compare / A-B** — ฟังโน้ตที่แกะได้เทียบเสียงจริง ⭐⭐⭐
4. **Practice Mode (Score Following)** — เสียบกีตาร์ผ่าน audio interface/ไมค์ → โปรแกรมจับ pitch ที่เล่น แล้วให้คะแนน/ไฮไลต์ตัวที่ผิด, โหมด "รอจนกว่าจะเล่นถูก" ⭐⭐
5. **Harmony Line Generator** — สร้างไลน์ประสาน 3rd/6th ในคีย์ สำหรับ twin guitar หรืออัดซ้อน ⭐⭐
6. **Fretboard Animation** — จุดโน้ตวิ่งบนคอกีตาร์ตามเพลง ดูตำแหน่งมือ ⭐⭐
7. **Tuner ในตัว** + ตรวจว่ากีตาร์จูนตรงกับ tuning offset ของเพลงไหม ⭐⭐
8. **Phrase Library** — เก็บ lick/วลีที่ชอบไว้เรียกใช้/ค้นหา ⭐
9. **Video Export** — วิดีโอแทปวิ่งพร้อมเพลง สำหรับลง YouTube/TikTok (Phase หลัง) ⭐
10. **Batch Mode** — ใส่หลายลิงก์ ให้ประมวลผลข้ามคืน ⭐
11. **Lyrics paste + forced alignment** — แม่นกว่า ASR มากสำหรับเพลงไทย ⭐⭐⭐ (แนะนำทำตั้งแต่ Phase แรกๆ)
12. **Melody simplifier** — ปุ่ม "ทำให้ง่ายลง" ตัดโน้ตประดับออก เหลือโครงหลัก สำหรับมือใหม่/คนดู ⭐⭐

---

## 23. Roadmap แบ่งเฟส

> หลัก: ทำ "เส้นทางหลัก" ให้ใช้งานได้จริงก่อน (ลิงก์ → โน้ต → แทป → รูป) แล้วค่อยเพิ่มความหรู

### Phase 0 — Setup & Spike (1 สัปดาห์)
- ติดตั้ง CUDA/PyTorch, ทดสอบโมเดลทีละตัวใน Jupyter: separation, RMVPE, CREPE, SOME, Beat This!, essentia, BTC, faster-whisper
- วัดเวลา/VRAM จริงบนเครื่อง → อัปเดตตาราง budget ในเอกสารนี้
- เตรียม **ชุดเพลงทดสอบ 10–20 เพลง** ที่แกะมือไว้แล้ว (ground truth) — ใช้วัดความแม่นตลอดโปรเจกต์
- ✅ Done เมื่อ: รันสคริปต์เดียว ได้ MIDI เมโลดี้จากลิงก์ YouTube

### Phase 1 — MVP หลังบ้าน + หน้าบ้านพื้นฐาน (2–3 สัปดาห์)
- FastAPI + Job Orchestrator + WebSocket progress + Status bar + System monitor
- Pipeline: ingest → separation (vocal) → f0 (RMVPE) → notes → key → beats
- React: Import, Piano Roll (แสดงโน้ต+ชื่อ+octave), เล่นเพลงพร้อม playhead
- Project save + cache พื้นฐาน
- ✅ Done เมื่อ: วางลิงก์ → เห็นโน้ตวิ่งพร้อมชื่อ และเห็น status ทุกขั้น

### Phase 2 — ความแม่นยำ (2–3 สัปดาห์) ⭐ สำคัญสุด
- Karaoke (lead/backing) + de-reverb
- f0 ensemble + octave correction + tuning offset
- SOME/HMM segmentation + key-aware quantization + rhythm quantization
- Confidence UI + A/B synth compare + แก้โน้ตใน piano roll
- Eval script (mir_eval) → ทำ benchmark ทุกครั้งที่ปรับ
- ✅ Done เมื่อ: Note F1 (onset) บนชุดทดสอบถึงเป้าที่ตั้ง (หัวข้อ 24)

### Phase 3 — Tab Engine + Editor (3 สัปดาห์)
- Candidate + Viterbi (Numba) + cost function + playability report + heatmap
- Block Mode (CAGED/3NPS/Pentatonic/Custom)
- Tab renderer (SVG) + Editor ทั้งหมดในหัวข้อ 14 + undo/redo + lock
- Easy key + capo suggestion
- ✅ Done เมื่อ: สร้างแทปได้ < 0.5 วินาที, จิ้มแก้ได้ทุกตัว

### Phase 4 — ทฤษฎีดนตรีครบ (2 สัปดาห์)
- Chords (BTC + bass root + smoothing), Sections (allin1), Time signature, Key change
- Lyrics (whisper + Thai alignment + paste lyrics) → Chord Sheet view
- Metronome ตาม beat grid + count-in + slow-down + loop

### Phase 5 — เทคนิคกีตาร์ + Export (2 สัปดาห์)
- Ornament detection → slide/bend/hammer/pull/vibrato/grace + กติกา feasibility
- Export รายท่อน PNG/SVG/PDF + templates + presets ขนาด
- Export MIDI / MusicXML / Guitar Pro / txt / stems

### Phase 6 — ขัดเกลา & ฟีเจอร์เสริม (ต่อเนื่อง)
- Tauri packaging เป็นตัวติดตั้ง Windows, Model Manager, history versions
- TensorRT/ONNX optimization, Practice Mode, Harmony generator, Fretboard animation, Batch mode, Video export

**รวมโดยประมาณ: 12–16 สัปดาห์** (ทำคนเดียวพาร์ทไทม์อาจนานกว่านี้ — ใช้ AI coding assistant ช่วยได้มาก)

---

## 24. การทดสอบและวัดความแม่นยำ

### 24.1 ชุดข้อมูล
- **ชุดส่วนตัว**: เพลงที่คุณแกะเองแล้ว (ดีที่สุด เพราะตรงสไตล์เพลงที่เล่นจริง เช่น เพลงไทย) → export เป็น MIDI ground truth
- ชุดสาธารณะสำหรับเทียบ: MIR-1K, MedleyDB (melody), และชุด singing transcription อื่นๆ (เช็กเงื่อนไข license)

### 24.2 Metrics (ใช้ `mir_eval`)
| สิ่งที่วัด | Metric | เป้าหมายเริ่มต้น (ปรับได้หลังวัดจริง) |
|---|---|---|
| f0 | Raw Pitch Accuracy (RPA), Raw Chroma Accuracy (RCA) | RPA > 90% บน vocal stem |
| โน้ต | Note F1 — COnP (onset+pitch), COnPOff (onset+pitch+offset) | COnP F1 > 80% |
| Key | ตรงคีย์ / relative / fifth | ตรงหรือ relative > 90% |
| Beat | F-measure | > 90% |
| Chord | Weighted Chord Symbol Recall (majmin) | > 75% |
| Tab | ความยากเฉลี่ย, % จุดแดง, เวลาที่ใช้แก้มือ | ลดลงทุกเวอร์ชัน |

### 24.3 การทดสอบอื่น
- Unit test: ทฤษฎีดนตรี (ชื่อโน้ต, transpose, enharmonic), tab engine (กรณีขอบ: โน้ตนอก range, block ว่าง)
- Regression: รัน benchmark อัตโนมัติก่อน merge ทุกครั้งที่แก้ pipeline
- **Metric ที่สำคัญที่สุดในชีวิตจริง**: "ใช้เวลาแก้มือกี่นาทีต่อเพลง" → จดเก็บไว้ทุกเพลง

---

## 25. ความเสี่ยงและข้อควรระวัง

| ความเสี่ยง | ผลกระทบ | การรับมือ |
|---|---|---|
| ไม่มีโมเดลไหนแม่น 100% | โน้ตผิดบางตัว | Human-in-the-loop, confidence, A/B, แก้ง่าย |
| เพลงที่ร้องประสานแน่น/เอฟเฟกต์เยอะ | lead vocal ไม่สะอาด | karaoke model, ให้เลือกช่วงแกะใหม่ด้วยโมเดลอื่น |
| Auto-tune / vocoder | pitch แบนผิดธรรมชาติ | จริงๆ ง่ายขึ้นสำหรับโน้ต แต่ ornament detection อาจพลาด |
| VRAM 8 GB ไม่พอบางโมเดล | OOM | chunk เล็กลง, bf16, รันทีละโมเดล, auto-retry |
| yt-dlp พังเมื่อ YouTube เปลี่ยนระบบ | ดาวน์โหลดไม่ได้ | ปุ่มอัปเดต yt-dlp ในแอป + รองรับลากไฟล์เสมอ |
| Whisper ภาษาไทยในเพลงพลาด | เนื้อผิด | ช่องวางเนื้อเอง + forced alignment |
| License โมเดล | บางโมเดล non-commercial | ใช้ส่วนตัวได้, ถ้าจะขาย/แจกต้องตรวจ license ทุกตัว |
| ลิขสิทธิ์เพลง/เงื่อนไข YouTube | ปัญหากฎหมายถ้าเผยแพร่ | ใช้เพื่อการเรียน/ส่วนตัว; ถ้าโพสต์แทปให้ตรวจข้อกำหนดของแพลตฟอร์มและสิทธิ์ของเพลง |
| Laptop ร้อน/throttle | ช้าลง | monitor อุณหภูมิ, โหมด performance, เสียบปลั๊ก |
| Scope ใหญ่ ทำไม่จบ | หมดไฟ | ยึด Roadmap ทำ MVP ใช้งานจริงก่อน แล้วค่อยเพิ่ม |

---

## ภาคผนวก A — สัญลักษณ์แทปที่ใช้

| สัญลักษณ์ | ความหมาย |
|---|---|
| `h` | Hammer-on |
| `p` | Pull-off |
| `/` `\` | Slide ขึ้น / ลง |
| `b` | Bend (เช่น `7b9` = bend ช่อง 7 ให้เสียงเท่าช่อง 9) |
| `r` | Release |
| `~` | Vibrato |
| `(n)` | Grace note |
| `x` | Muted / dead note |
| `PM` | Palm mute |
| `let ring` | ปล่อยเสียงค้าง |

## ภาคผนวก B — ระบบชื่อโน้ต
- Scientific Pitch Notation: Middle C = **C4**, A4 = 440 Hz (MIDI 69)
- กีตาร์ standard tuning (เสียงจริง): E2 A2 D3 G3 B3 E4, ช่อง 12 สาย 1 = E5
- ♯/♭ เลือกตามคีย์อัตโนมัติ (คีย์ที่มี ♭ แสดงเป็น ♭)
- โหมดแสดงทางเลือก: ชื่อสากล / โด-เร-มี / scale degree / ตัวเลขช่องบนกีตาร์

---
*เอกสารนี้เป็น living document — อัปเดตตัวเลข VRAM/เวลา/ความแม่นหลังจบ Phase 0 และทุกครั้งที่เปลี่ยนโมเดล*
