"""path และค่าคงที่กลางของ backend"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # D:\melotab
MODELS_DIR = ROOT / "models"
THIRD_PARTY = ROOT / "third_party"

SOME_DIR = THIRD_PARTY / "SOME"
SOME_CKPT = MODELS_DIR / "SOME" / "0119_continuous256_5spk" / "model_ckpt_steps_100000_simplified.ckpt"
RMVPE_CKPT = MODELS_DIR / "RMVPE" / "model.pt"

# โมเดลแยกเสียงผ่าน audio-separator (ชื่อไฟล์ตามรายการของ audio-separator)
SEP_VOCAL_MODEL = "vocals_mel_band_roformer.ckpt"
SEP_KARAOKE_MODEL = "mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt"
SEP_DEREVERB_MODEL = "dereverb_mel_band_roformer_anvuew_sdr_19.1729.ckpt"

ANALYSIS_SR = 44100       # sample rate ของไฟล์เสียงที่ใช้ในระบบ
F0_HOP_S = 0.010          # f0 ทุก 10 ms
