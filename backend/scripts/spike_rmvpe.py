"""Spike Phase 0: RMVPE vs torchcrepe บน vocal stem เดียวกัน + ตัดสินโน้ตที่ SOME กับ crepe ต่าง octave
ใช้โค้ด RMVPE ใน third_party/SOME (modules.rmvpe) + น้ำหนัก models/RMVPE/model.pt
รัน:  python spike_rmvpe.py VOCAL_AUDIO SOME_MIDI   (รันด้วย .venv-spike, cwd ใดก็ได้)"""
import sys, time, threading, collections
sys.path.insert(0, r"D:\melotab\third_party\SOME")
import numpy as np, torch, torchcrepe, librosa, mido, pynvml
from scipy.ndimage import binary_opening
from modules.rmvpe.inference import RMVPE

stem, midi_path = sys.argv[1], sys.argv[2]
y, _ = librosa.load(stem, sr=16000, mono=True)

pynvml.nvmlInit(); h = pynvml.nvmlDeviceGetHandleByIndex(0)
base = pynvml.nvmlDeviceGetMemoryInfo(h).used / 2**20; peak = [base]; stop = threading.Event()
def poll():
    while not stop.is_set():
        peak[0] = max(peak[0], pynvml.nvmlDeviceGetMemoryInfo(h).used / 2**20); time.sleep(0.1)
threading.Thread(target=poll, daemon=True).start()

t0 = time.time()
rm = RMVPE(r"D:\melotab\models\RMVPE\model.pt", hop_length=160)
t1 = time.time()
f0_r = rm.infer_from_audio(y, sample_rate=16000, thred=0.03, use_viterbi=False)
torch.cuda.synchronize(); t2 = time.time(); stop.set()
print(f"RMVPE load={t1-t0:.1f}s infer={t2-t1:.1f}s vram_delta={peak[0]-base:.0f}MB frames={len(f0_r)}")

f0_c, per = torchcrepe.predict(torch.from_numpy(y)[None].to("cuda"), 16000, 160, 50, 1100, "full", batch_size=512,
                               device="cuda", return_periodicity=True, decoder=torchcrepe.decode.viterbi)
f0_c, per = f0_c[0].cpu().numpy(), per[0].cpu().numpy()
n = min(len(f0_r), len(f0_c)); f0_r, f0_c, per = f0_r[:n], f0_c[:n], per[:n]
v_c = binary_opening(per > 0.21, structure=np.ones(3)); v_r = f0_r > 0
print(f"voiced: rmvpe={v_r.mean()*100:.0f}% crepe={v_c.mean()*100:.0f}%  both={np.mean(v_r & v_c)*100:.0f}%")
both = v_r & v_c
d = librosa.hz_to_midi(f0_r[both]) - librosa.hz_to_midi(f0_c[both])
print(f"rmvpe-crepe on shared voiced frames: median={np.median(d):+.2f} st, |d|<0.5: {np.mean(np.abs(d)<0.5)*100:.1f}%, "
      f"|d|>=11 (octave): {np.mean(np.abs(d)>=11)*100:.2f}% ({np.sum(np.abs(d)>=11)} frames)")

# --- โน้ต SOME ---
notes, on, t = [], {}, 0.0
for m in mido.MidiFile(midi_path):
    t += m.time
    if m.type == "note_on" and m.velocity > 0: on[m.note] = t
    elif m.type in ("note_off", "note_on") and m.note in on: notes.append((on.pop(m.note), t, m.note))
tf = np.arange(n) * 0.010
fr = np.where(v_r, librosa.hz_to_midi(np.maximum(f0_r, 1)), np.nan)
fc = np.where(v_c, librosa.hz_to_midi(np.maximum(f0_c, 1)), np.nan)
res = collections.Counter(); ex = []
for s, e, p in notes:
    m_ = (tf >= s) & (tf < e)
    a, b = fr[m_], fc[m_]; a, b = a[~np.isnan(a)], b[~np.isnan(b)]
    if len(a) < 3 or len(b) < 3: continue
    dr, dc = np.median(a) - p, np.median(b) - p
    if abs(dc) >= 11:                      # โน้ตที่ crepe ต่างจาก SOME ≥ 1 octave
        k = "rmvpe ตรง crepe (SOME ผิด?)" if abs(dr - dc) < 1 else ("rmvpe ตรง SOME (crepe ผิด?)" if abs(dr) < 1 else "rmvpe ต่างจากทั้งคู่")
        res[k] += 1
        if len(ex) < 6: ex.append((round(s, 1), librosa.midi_to_note(p), librosa.midi_to_note(np.median(b)), librosa.midi_to_note(np.median(a)), k))
print("โน้ตที่ SOME vs crepe ต่าง ≥ octave:", dict(res))
for e_ in ex: print("  ", e_)
dr_all = np.array([np.median(fr[(tf>=s)&(tf<e)][~np.isnan(fr[(tf>=s)&(tf<e)])]) - p for s, e, p in notes
                   if np.sum(~np.isnan(fr[(tf>=s)&(tf<e)])) >= 3])
print(f"SOME vs RMVPE: mean|d|={np.abs(dr_all).mean():.2f} within±1={np.mean(np.abs(dr_all)<=1)*100:.0f}% octave(|d|>=11)={np.sum(np.abs(dr_all)>=11)} / {len(dr_all)}")
