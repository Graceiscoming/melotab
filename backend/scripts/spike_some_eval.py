"""Spike Phase 0: ประเมินโน้ตจาก SOME (MIDI) เทียบกับ f0 ของ torchcrepe + สร้างไฟล์ฟังเทียบ (ซ้าย=vocal, ขวา=โน้ต SOME)"""
import sys
import numpy as np, torch, torchcrepe, librosa, mido, soundfile as sf
from scipy.ndimage import binary_opening

stem, midi_path, out_wav = sys.argv[1], sys.argv[2], sys.argv[3]

# --- โน้ตจาก MIDI (หน่วยวินาที) ---
notes, on, t = [], {}, 0.0
for msg in mido.MidiFile(midi_path):
    t += msg.time
    if msg.type == "note_on" and msg.velocity > 0:
        on[msg.note] = t
    elif msg.type in ("note_off", "note_on") and msg.note in on:
        notes.append((on.pop(msg.note), t, msg.note))
notes.sort()
dur = np.array([e - s for s, e, _ in notes]); pit = np.array([p for *_, p in notes])

# --- f0 อ้างอิง ---
y16, _ = librosa.load(stem, sr=16000, mono=True)
f0, per = torchcrepe.predict(torch.from_numpy(y16)[None].to("cuda"), 16000, 160, 50, 1100, "full", batch_size=512,
                             device="cuda", return_periodicity=True, decoder=torchcrepe.decode.viterbi)
f0, per = f0[0].cpu().numpy(), per[0].cpu().numpy()
voiced = binary_opening(per > 0.21, structure=np.ones(3))
fm = np.where(voiced, librosa.hz_to_midi(np.maximum(f0, 1)), np.nan)
tf = np.arange(len(f0)) * 0.010

# --- เทียบโน้ตกับ median f0 ในช่วงโน้ต ---
diffs, nov = [], 0
for s, e, p in notes:
    seg = fm[(tf >= s) & (tf < e)]
    seg = seg[~np.isnan(seg)]
    if len(seg) < 3: nov += 1; continue
    diffs.append(np.median(seg) - p)
diffs = np.array(diffs)
cov_frames = np.zeros(len(f0), bool)
for s, e, _ in notes: cov_frames[(tf >= s) & (tf < e)] = True
print(f"notes={len(notes)} total_dur={dur.sum():.1f}s median_dur={np.median(dur)*1000:.0f}ms min={dur.min()*1000:.0f}ms max={dur.max():.2f}s")
print(f"pitch range {librosa.midi_to_note(pit.min())}-{librosa.midi_to_note(pit.max())}, notes with no voiced f0 inside: {nov}")
print(f"note vs median-f0 (semitones): mean={diffs.mean():+.2f} mean|d|={np.abs(diffs).mean():.2f} "
      f"within±0.5={np.mean(np.abs(diffs)<=0.5)*100:.0f}% within±1={np.mean(np.abs(diffs)<=1.0)*100:.0f}% "
      f"octave-ish(|d|>=11)={np.sum(np.abs(diffs)>=11)}")
print(f"voiced frames covered by a note: {cov_frames[voiced].mean()*100:.0f}%  | note frames that are unvoiced: {(~voiced[cov_frames]).mean()*100:.0f}%")
print("first 15 notes (start s, dur ms, name):", [(round(s,2), round((e-s)*1000), librosa.midi_to_note(p)) for s,e,p in notes[:15]])

# --- ไฟล์ฟังเทียบ ---
SR = 44100
ystem, _ = librosa.load(stem, sr=SR, mono=True)
n = len(ystem); wave = np.zeros(n)
for s, e, p in notes:
    i0, i1 = int(s*SR), min(int(e*SR), n)
    k = np.arange(i1-i0) / SR
    f = librosa.midi_to_hz(p)
    w = np.sin(2*np.pi*f*k) + 0.35*np.sin(4*np.pi*f*k) + 0.15*np.sin(6*np.pi*f*k)
    a = np.minimum(1, np.minimum(k, k[-1]-k)/0.01 + 0.0)
    wave[i0:i1] += 0.22 * w * a
sf.write(out_wav, np.stack([ystem/(np.abs(ystem).max()+1e-9)*0.8, wave], 1), SR, subtype="PCM_16")
print("wrote", out_wav)
