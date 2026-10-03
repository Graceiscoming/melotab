"""Spike Phase 0: f0 ด้วย torchcrepe (full, viterbi) บน vocal stem วัดเวลา + VRAM แล้วสรุปช่วงเสียง"""
import sys, time, threading
import numpy as np, torch, torchcrepe, librosa, pynvml

path = sys.argv[1]
y, sr = librosa.load(path, sr=16000, mono=True)

pynvml.nvmlInit(); h = pynvml.nvmlDeviceGetHandleByIndex(0)
base = pynvml.nvmlDeviceGetMemoryInfo(h).used / 2**20
peak = [base]; stop = threading.Event()
def poll():
    while not stop.is_set():
        peak[0] = max(peak[0], pynvml.nvmlDeviceGetMemoryInfo(h).used / 2**20); time.sleep(0.1)
threading.Thread(target=poll, daemon=True).start()

x = torch.from_numpy(y)[None].to("cuda")
hop = int(sr * 0.010)
torch.cuda.synchronize(); t0 = time.time()
f0, per = torchcrepe.predict(x, sr, hop, 50, 1100, "full", batch_size=512, device="cuda",
                             return_periodicity=True, decoder=torchcrepe.decode.viterbi)
torch.cuda.synchronize(); dt = time.time() - t0
stop.set()
f0 = f0[0].cpu().numpy(); per = per[0].cpu().numpy()
voiced = per > 0.21
midi = librosa.hz_to_midi(f0[voiced])
names = librosa.midi_to_note(np.round(midi))
print(f"RESULT dur={len(y)/sr:.1f}s f0_time={dt:.1f}s frames={len(f0)} voiced={voiced.mean()*100:.0f}% "
      f"vram_base={base:.0f}MB vram_peak={peak[0]:.0f}MB delta={peak[0]-base:.0f}MB")
print("range:", librosa.midi_to_note(np.percentile(midi, 2)), "-", librosa.midi_to_note(np.percentile(midi, 98)),
      "| median:", librosa.midi_to_note(np.median(midi)))
u, c = np.unique(names, return_counts=True)
print("top notes:", ", ".join(f"{n}:{k}" for n, k in sorted(zip(u, c), key=lambda t: -t[1])[:8]))
