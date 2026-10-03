"""f0 ของเสียงร้องด้วย RMVPE (หลัก, เร็ว ~2 s/เพลง 4:50) — ใช้คลาส RMVPE ที่มากับ third_party/SOME"""
import sys

import librosa
import numpy as np

from ..config import F0_HOP_S, RMVPE_CKPT, SOME_DIR
from ..gpu import free_gpu


def extract_f0(wav_path) -> dict:
    """คืน {'f0_hz': float32[n] (0 = unvoiced), 'hop_s': 0.01, 'times': float32[n]}"""
    if str(SOME_DIR) not in sys.path:
        sys.path.insert(0, str(SOME_DIR))
    from modules.rmvpe.inference import RMVPE  # noqa: E402  (โค้ดจาก repo SOME)

    y, _ = librosa.load(str(wav_path), sr=16000, mono=True)
    model = RMVPE(str(RMVPE_CKPT), hop_length=160)
    try:
        f0 = model.infer_from_audio(y, sample_rate=16000, thred=0.03, use_viterbi=False)
    finally:
        del model
        free_gpu()
    f0 = np.asarray(f0, dtype=np.float32)
    return {"f0_hz": f0, "hop_s": F0_HOP_S, "times": (np.arange(len(f0)) * F0_HOP_S).astype(np.float32)}
