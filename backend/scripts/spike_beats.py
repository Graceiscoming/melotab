"""Spike Phase 0: Beat This! บนเพลงเต็ม — วัดเวลา/VRAM, สรุป BPM/จังหวะต่อห้อง และสร้างไฟล์ฟัง (เพลง + เสียงเคาะ downbeat/beat)
รัน (.venv-spike):  python spike_beats.py AUDIO OUT_WAV"""
import sys, time, threading
import numpy as np, librosa, soundfile as sf, pynvml
from beat_this.inference import File2Beats

audio, out_wav = sys.argv[1], sys.argv[2]
pynvml.nvmlInit(); h = pynvml.nvmlDeviceGetHandleByIndex(0)
base = pynvml.nvmlDeviceGetMemoryInfo(h).used / 2**20; peak = [base]; stop = threading.Event()
def poll():
    while not stop.is_set():
        peak[0] = max(peak[0], pynvml.nvmlDeviceGetMemoryInfo(h).used / 2**20); time.sleep(0.1)
threading.Thread(target=poll, daemon=True).start()

t0 = time.time(); f2b = File2Beats(device="cuda", dbn=False); t1 = time.time()
beats, downbeats = f2b(audio); t2 = time.time(); stop.set()
print(f"load(+ดาวน์โหลดโมเดลครั้งแรก)={t1-t0:.1f}s infer={t2-t1:.1f}s vram_delta={peak[0]-base:.0f}MB")

ibi = np.diff(beats); bpm = 60 / ibi
print(f"beats={len(beats)} downbeats={len(downbeats)} first_beat={beats[0]:.2f}s last={beats[-1]:.1f}s")
print(f"BPM median={np.median(bpm):.1f}  p5-p95={np.percentile(bpm,5):.1f}-{np.percentile(bpm,95):.1f}  std={bpm.std():.1f}")
# จำนวน beat ต่อห้อง (นับ beat ระหว่าง downbeat)
per_bar = [int(np.sum((beats >= a - 1e-3) & (beats < b - 1e-3))) for a, b in zip(downbeats[:-1], downbeats[1:])]
vals, cnt = np.unique(per_bar, return_counts=True)
print("beats/bar:", dict(zip(vals.tolist(), cnt.tolist())), "-> time signature น่าจะเป็น", f"{vals[np.argmax(cnt)]}/4 (ถ้าเป็นเพลง 4/4 ปกติ)")
# tempo ต่อ 30 วินาที
for a in range(0, int(beats[-1]), 30):
    m = (beats[:-1] >= a) & (beats[:-1] < a + 30)
    if m.sum() > 3: print(f"  {a:>3}-{a+30}s BPM≈{60/np.median(ibi[m]):.1f}")

# ไฟล์ฟัง: เพลง + คลิก (downbeat = สูง, beat = ต่ำ)
y, sr = librosa.load(audio, sr=44100, mono=True)
click = np.zeros_like(y)
def add(t, f, a):
    i = int(t * sr); k = np.arange(int(0.05 * sr)) / sr
    seg = a * np.sin(2*np.pi*f*k) * np.exp(-k*60); click[i:i+len(seg)] += seg[:max(0, len(click)-i)]
db = set(np.round(downbeats, 3).tolist())
for b in beats: add(b, 1800 if round(b, 3) in db or np.min(np.abs(downbeats - b)) < 0.03 else 1000, 0.5)
sf.write(out_wav, np.stack([y * 0.6, click], 1), sr, subtype="PCM_16")
print("wrote", out_wav, "(ซ้าย=เพลง, ขวา=เสียงเคาะ)")
