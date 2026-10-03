"""beat / downbeat ด้วย Beat This! + ประมาณ BPM

Phase 0 พบว่า Beat This! อาจสลับ tempo ครึ่ง/เท่าตัวเป็นช่วง ๆ (≈128 ↔ ≈64 BPM) จึงรายงาน `tempo_unstable`
และ BPM ที่พับเข้าช่วง 70–160 ให้ UI เสนอปุ่ม ×2/÷2 — ยังไม่ได้ทำ tempo normalization ของ beat grid จริง
"""
import numpy as np

from ..gpu import free_gpu


def _fold(bpm: float, lo: float = 70.0, hi: float = 160.0) -> float:
    while bpm < lo:
        bpm *= 2
    while bpm > hi:
        bpm /= 2
    return bpm


def analyze_rhythm(audio_path) -> dict:
    from beat_this.inference import File2Beats

    f2b = File2Beats(device="cuda", dbn=False)
    try:
        beats, downbeats = f2b(str(audio_path))
    finally:
        del f2b
        free_gpu()
    beats = np.asarray(beats, dtype=float)
    downbeats = np.asarray(downbeats, dtype=float)
    if len(beats) < 4:
        return {"beats": [], "bpm": None, "tempo_unstable": True, "time_signature": None}

    ibi = np.diff(beats)
    bpm_local = 60.0 / ibi
    folded = np.array([_fold(b) for b in bpm_local])
    bpm_raw_median = float(np.median(bpm_local))
    bpm = float(np.median(folded))
    # ไม่เสถียร = BPM ดิบสลับกันเกินเท่าตัวจริง ๆ (ratio ของ p95/p5 > 1.6)
    unstable = float(np.percentile(bpm_local, 95) / np.percentile(bpm_local, 5)) > 1.6

    # beat ต่อห้อง → time signature (โหวตตามที่พบมากสุด)
    per_bar = [int(np.sum((beats >= a - 1e-3) & (beats < b - 1e-3))) for a, b in zip(downbeats[:-1], downbeats[1:])]
    num = int(np.bincount(per_bar).argmax()) if per_bar else 4

    out, bar, beat_in_bar, di = [], 0, 0, 0
    for t in beats:
        if di < len(downbeats) and abs(t - downbeats[di]) < 0.03:
            bar += 1; beat_in_bar = 1; di += 1
        else:
            beat_in_bar += 1
        out.append({"time": round(float(t), 3), "bar": max(bar, 1), "beat": max(beat_in_bar, 1)})
    return {"beats": out, "bpm": round(bpm, 1), "bpm_raw_median": round(bpm_raw_median, 1),
            "tempo_unstable": unstable, "time_signature": {"num": num, "den": 4}}
