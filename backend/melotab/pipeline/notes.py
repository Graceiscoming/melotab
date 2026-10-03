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


def estimate_tuning(f0: dict) -> float:
    """ค่า tuning offset ของเพลง (cents, -50..+50) เทียบ A=440 จากส่วนเกินครึ่งเสียงของ f0 ทุกเฟรมที่ voiced

    ใช้ฮิสโทแกรมของ (cents ห่างจากครึ่งเสียงที่ใกล้สุด) แล้วเอายอดที่เด่นสุด (ทนต่อ vibrato/ลูกคอกว่าค่าเฉลี่ย)
    เสียงร้องไม่นิ่งเท่าเครื่องดนตรี ค่านี้จึงหยาบ (± ~10 cents) และถ้าเฟรมน้อยเกินไปจะคืน 0
    """
    hz = f0["f0_hz"]
    hz = hz[hz > 0]
    if len(hz) < 200:
        return 0.0
    dev = (librosa.hz_to_midi(hz) % 1.0)
    dev = np.where(dev >= 0.5, dev - 1.0, dev) * 100.0          # -50..+50 cents
    hist, edges = np.histogram(dev, bins=50, range=(-50, 50))
    k = np.convolve(hist, np.ones(3) / 3, mode="same")          # ทำให้เรียบกันยอดสุ่ม
    peak = int(np.argmax(k))
    return round(float((edges[peak] + edges[peak + 1]) / 2), 1)


def annotate(notes: list[dict], f0: dict, *, fix_octave: bool = True, tuning_cents: float = 0.0) -> list[dict]:
    """ติด cents_offset / confidence / octave_suspect จาก f0 (RMVPE)

    fix_octave: ถ้า median f0 ในช่วงโน้ตต่างจากโน้ตเป็นพหุคูณของ 12 semitone (±1) จะย้ายโน้ตไป octave ของ f0
    (Phase 0: เสียงประสานใน vocal stem ทำให้ SOME จับผิด octave) — ติดธง `octave_fixed` ให้ผู้ใช้ตรวจ/ย้อนได้
    tuning_cents: ชดเชย tuning ของเพลงก่อนคำนวณ cents_offset (ค่านี้ไม่เปลี่ยนชื่อโน้ต)
    """
    times, hz = f0["times"], f0["f0_hz"]
    midi_f0 = np.where(hz > 0, librosa.hz_to_midi(np.maximum(hz, 1.0)) - tuning_cents / 100.0, np.nan)
    out = []
    for i, n in enumerate(notes, 1):
        midi = n["midi"]
        m = (times >= n["start"]) & (times < n["end"])
        seg = midi_f0[m]
        seg = seg[~np.isnan(seg)]
        voiced_ratio = float(len(seg) / max(1, m.sum()))
        octave_fixed = False
        if len(seg) < 3:
            cents, conf, octave = None, 0.2, False
        else:
            d = float(np.median(seg)) - midi
            octave = abs(d) >= OCTAVE_SEMITONES
            if octave and fix_octave:
                shift = round(d / 12.0) * 12
                if abs(d - shift) <= 1.0:                       # ต่างกันเกือบเป๊ะเป็น octave → ย้ายตาม f0
                    midi += int(shift)
                    d -= shift
                    octave, octave_fixed = False, True
            cents = round((d - round(d)) * 100) if not octave else None
            conf = float(np.clip(1.0 - abs(d) / 1.5, 0.1, 1.0)) * (0.5 + 0.5 * min(1.0, voiced_ratio))
            if octave_fixed:
                conf = min(conf, 0.6)                           # ผ่านการแก้อัตโนมัติ ควรให้คนตรวจ
        out.append({
            "id": f"n{i}", "midi": midi, "name": _note_name(midi),
            "freq": round(float(librosa.midi_to_hz(midi)), 2),
            "start": n["start"], "end": n["end"],
            "cents_offset": cents, "confidence": round(conf, 3),
            "octave_suspect": bool(octave), "octave_fixed": octave_fixed, "edited": False,
        })
    return out


def refine(notes: list[dict], *, min_dur_ms: float = 0.0, merge_gap_ms: float = 0.0) -> list[dict]:
    """ปรับความละเอียดของโน้ตดิบ (slider "ละเอียด ↔ เรียบ" ใน plan หัวข้อ 7)

    - รวมโน้ตติดกันที่ pitch เดียวกัน เมื่อช่องว่าง ≤ merge_gap_ms (ถ้า merge_gap_ms = 0 จะไม่รวมเลย เพราะการร้องโน้ตเดิมซ้ำติดกันเป็นโน้ตคนละตัว)
    - ตัดโน้ตที่สั้นกว่า min_dur_ms (ทำหลังรวม)
    """
    out: list[dict] = []
    for n in sorted(notes, key=lambda x: x["start"]):
        if merge_gap_ms > 0 and out and out[-1]["midi"] == n["midi"] and (n["start"] - out[-1]["end"]) * 1000 <= merge_gap_ms:
            out[-1] = {**out[-1], "end": max(out[-1]["end"], n["end"])}
        else:
            out.append(dict(n))
    return [n for n in out if (n["end"] - n["start"]) * 1000 >= min_dur_ms]
