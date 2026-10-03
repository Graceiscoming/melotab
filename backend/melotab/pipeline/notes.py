"""แบ่งโน้ตด้วย SOME แล้วติด confidence แบบ heuristic จากความสอดคล้องกับ f0 ของ RMVPE

หมายเหตุ: confidence ที่นี่ "ไม่ใช่ความน่าจะเป็นจากโมเดล" แต่คำนวณจากว่าโน้ตตรงกับ median f0 ในช่วงนั้นแค่ไหน
(SOME ไม่ได้ให้ confidence) — ใช้เป็นสัญญาณให้คนตรวจ (plan หัวข้อ 7) ยังไม่ผ่านการวัดกับ ground truth
"""
import pathlib
import sys

import librosa
import numpy as np
import yaml

from ..config import SOME_CKPT, SOME_DIR
from ..gpu import free_gpu

OCTAVE_SEMITONES = 11.0


def _note_name(midi: int) -> str:
    return librosa.midi_to_note(int(midi), unicode=False)


def transcribe(wav_path) -> list[dict]:
    """คืนโน้ตดิบ [{'midi', 'start', 'end'}] หน่วยวินาที (ตัดช่วงพักออก)"""
    if str(SOME_DIR) not in sys.path:
        sys.path.insert(0, str(SOME_DIR))
    import importlib

    import inference  # noqa: E402  (แพ็กเกจ inference ของ repo SOME)
    from utils.slicer2 import Slicer  # noqa: E402

    ckpt = pathlib.Path(SOME_CKPT)
    with open(ckpt.with_name("config.yaml"), "r", encoding="utf8") as f:
        config = yaml.safe_load(f)
    path = inference.task_inference_mapping[config["task_cls"]]
    cls = getattr(importlib.import_module(".".join(path.split(".")[:-1])), path.split(".")[-1])
    infer = cls(config=config, model_path=ckpt)
    try:
        sr = config["audio_sample_rate"]
        wave, _ = librosa.load(str(wav_path), sr=sr, mono=True)
        chunks = Slicer(sr=sr, max_sil_kept=1000).slice(wave)
        results = infer.infer([c["waveform"] for c in chunks])
    finally:
        del infer
        free_gpu()

    notes = []
    offsets = [c["offset"] for c in chunks]
    for i, (off, seg) in enumerate(zip(offsets, results)):
        limit = offsets[i + 1] if i + 1 < len(offsets) else float("inf")
        t = off
        for midi, dur, rest in zip(seg["note_midi"], seg["note_dur"], seg["note_rest"]):
            end = min(t + float(dur), limit)
            if not rest and end > t:
                notes.append({"midi": int(round(float(midi))), "start": round(t, 4), "end": round(end, 4)})
            t += float(dur)
    return notes


def annotate(notes: list[dict], f0: dict) -> list[dict]:
    """ติด cents_offset / confidence / octave_suspect จาก f0 (RMVPE)"""
    times, hz = f0["times"], f0["f0_hz"]
    midi_f0 = np.where(hz > 0, librosa.hz_to_midi(np.maximum(hz, 1.0)), np.nan)
    out = []
    for i, n in enumerate(notes, 1):
        m = (times >= n["start"]) & (times < n["end"])
        seg = midi_f0[m]
        seg = seg[~np.isnan(seg)]
        voiced_ratio = float(len(seg) / max(1, m.sum()))
        if len(seg) < 3:
            cents, conf, octave = None, 0.2, False
        else:
            d = float(np.median(seg)) - n["midi"]
            octave = abs(d) >= OCTAVE_SEMITONES
            cents = round((d - round(d)) * 100) if not octave else None
            conf = float(np.clip(1.0 - abs(d) / 1.5, 0.1, 1.0)) * (0.5 + 0.5 * min(1.0, voiced_ratio))
        out.append({
            "id": f"n{i}", "midi": n["midi"], "name": _note_name(n["midi"]),
            "freq": round(float(librosa.midi_to_hz(n["midi"])), 2),
            "start": n["start"], "end": n["end"],
            "cents_offset": cents, "confidence": round(conf, 3),
            "octave_suspect": bool(octave), "edited": False,
        })
    return out
