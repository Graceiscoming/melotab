"""Spike Phase 0: สร้างไฟล์ฟังเทียบ — ช่องซ้าย = vocal stem, ช่องขวา = เสียงสังเคราะห์จาก f0
สร้าง 2 ไฟล์: raw (ตาม f0 จริง) และ snapped (ปัดเป็นครึ่งเสียง ให้ได้ยินว่าโน้ตที่แกะจะฟังเป็นยังไง)"""
import sys
import numpy as np, torch, torchcrepe, librosa, soundfile as sf
from scipy.ndimage import binary_opening, uniform_filter1d

stem, outprefix = sys.argv[1], sys.argv[2]
SR = 44100
y16, _ = librosa.load(stem, sr=16000, mono=True)
x = torch.from_numpy(y16)[None].to("cuda")
f0, per = torchcrepe.predict(x, 16000, 160, 50, 1100, "full", batch_size=512, device="cuda",
                             return_periodicity=True, decoder=torchcrepe.decode.viterbi)
f0, per = f0[0].cpu().numpy(), per[0].cpu().numpy()
voiced = binary_opening(per > 0.21, structure=np.ones(3))   # ตัดช่วง voiced สั้นๆ ที่เป็น noise

ystem, _ = librosa.load(stem, sr=SR, mono=True)
n = len(ystem)
t_frames = np.arange(len(f0)) * 0.010
t = np.arange(n) / SR
rms = librosa.feature.rms(y=ystem, frame_length=2048, hop_length=441)[0]
env = np.interp(t, np.arange(len(rms)) * 0.010, rms)
env = env / (np.percentile(env, 95) + 1e-9)

def synth(f0_hz):
    f = np.interp(t, t_frames, np.where(voiced, f0_hz, np.nan * 0 + 0))
    v = np.interp(t, t_frames, voiced.astype(float))
    v = uniform_filter1d(v, int(SR * 0.01))                  # fade เข้า/ออกเล็กน้อย กันเสียงแตก
    f = np.where(f > 0, f, 220.0)
    ph = 2 * np.pi * np.cumsum(f) / SR
    wave = np.sin(ph) + 0.35 * np.sin(2 * ph) + 0.15 * np.sin(3 * ph)
    return 0.25 * wave * v * np.clip(env, 0.3, 1.2)

f0_safe = np.where(voiced, f0, 0.0)
raw = synth(f0_safe)
snapped_hz = np.where(f0_safe > 0, librosa.midi_to_hz(np.round(librosa.hz_to_midi(np.maximum(f0_safe, 1)))), 0.0)
snapped = synth(snapped_hz)

peak_v = np.max(np.abs(ystem)) + 1e-9
for name, s in (("raw", raw), ("snapped", snapped)):
    out = np.stack([ystem / peak_v * 0.8, s], axis=1)
    sf.write(f"{outprefix}_{name}.wav", out, SR, subtype="PCM_16")
    print("wrote", f"{outprefix}_{name}.wav")
print(f"voiced frames {voiced.mean()*100:.0f}% of {len(f0)}")
