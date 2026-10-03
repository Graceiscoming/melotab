"""วัดความแม่นยำด้วย mir_eval (plan หัวข้อ 24): Note F1 (COnP / COnPOff) และ f0 (RPA / RCA)

ground truth = MIDI (หรือ song.json) ที่ผู้ใช้แกะมือไว้
    python -m melotab.evaluate --ref แกะมือ.mid --est Projects/<id>/song.json

หมายเหตุ: เวลาใน MIDI ต้องเป็นเวลาจริง (วินาที) — MIDI ที่ export จาก MeloTab ใช้ tempo 120 BPM คงที่ ถ้า ground truth
ของคุณใช้ tempo อื่นหรือมี tempo map ให้ mido แปลงเป็นวินาทีให้เองตาม tempo ในไฟล์
"""
import argparse
import json
from pathlib import Path

import mido
import numpy as np
import mir_eval


def load_notes(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """คืน (intervals [n,2] วินาที, pitches Hz [n]) จาก .mid หรือ song.json"""
    path = Path(path)
    if path.suffix.lower() == ".json":
        notes = json.loads(path.read_text(encoding="utf-8"))["notes"]
        iv = np.array([[n["start"], n["end"]] for n in notes], dtype=float).reshape(-1, 2)
        hz = np.array([440.0 * 2 ** ((n["midi"] - 69) / 12) for n in notes], dtype=float)
        return iv, hz
    on: dict[int, float] = {}
    out, t = [], 0.0
    for m in mido.MidiFile(path):
        t += m.time
        if m.type == "note_on" and m.velocity > 0:
            on[m.note] = t
        elif m.type in ("note_off", "note_on") and m.note in on:
            out.append((on.pop(m.note), t, m.note))
    out.sort()
    iv = np.array([[a, b] for a, b, _ in out], dtype=float).reshape(-1, 2)
    hz = np.array([440.0 * 2 ** ((p - 69) / 12) for *_, p in out], dtype=float)
    return iv, hz


def evaluate_notes(ref: tuple[np.ndarray, np.ndarray], est: tuple[np.ndarray, np.ndarray],
                   onset_tol: float = 0.05, pitch_tol_cents: float = 50.0) -> dict:
    """COnP = onset ±50 ms + pitch ±50 cents; COnPOff เพิ่มเงื่อนไข offset (ยอมคลาด 20% ของความยาว หรือ ≥ 50 ms)"""
    (ri, rp), (ei, ep) = ref, est
    if len(ri) == 0 or len(ei) == 0:
        return {"COnP": {"precision": 0.0, "recall": 0.0, "f1": 0.0}, "COnPOff": {"precision": 0.0, "recall": 0.0, "f1": 0.0},
                "n_ref": int(len(ri)), "n_est": int(len(ei))}
    p, r, f, _ = mir_eval.transcription.precision_recall_f1_overlap(ri, rp, ei, ep, onset_tolerance=onset_tol,
                                                                    pitch_tolerance=pitch_tol_cents, offset_ratio=None)
    po, ro, fo, _ = mir_eval.transcription.precision_recall_f1_overlap(ri, rp, ei, ep, onset_tolerance=onset_tol,
                                                                       pitch_tolerance=pitch_tol_cents, offset_ratio=0.2)
    return {"COnP": {"precision": p, "recall": r, "f1": f}, "COnPOff": {"precision": po, "recall": ro, "f1": fo},
            "n_ref": int(len(ri)), "n_est": int(len(ei))}


def evaluate_f0(ref_t: np.ndarray, ref_hz: np.ndarray, est_t: np.ndarray, est_hz: np.ndarray) -> dict:
    """RPA/RCA/OA ของ mir_eval.melody (เสียง unvoiced ใช้ 0 Hz)"""
    res = mir_eval.melody.evaluate(ref_t, ref_hz, est_t, est_hz)
    return {"RPA": res["Raw Pitch Accuracy"], "RCA": res["Raw Chroma Accuracy"], "OA": res["Overall Accuracy"],
            "VR": res["Voicing Recall"], "VFA": res["Voicing False Alarm"]}


def main() -> None:
    ap = argparse.ArgumentParser(prog="melotab.evaluate")
    ap.add_argument("--ref", type=Path, required=True, help="ground truth (.mid หรือ song.json)")
    ap.add_argument("--est", type=Path, required=True, help="ผลที่ได้ (.mid หรือ song.json)")
    ap.add_argument("--onset-tol", type=float, default=0.05)
    a = ap.parse_args()
    res = evaluate_notes(load_notes(a.ref), load_notes(a.est), onset_tol=a.onset_tol)
    print(f"โน้ต ref={res['n_ref']} est={res['n_est']}")
    for k in ("COnP", "COnPOff"):
        v = res[k]
        print(f"{k}: P={v['precision']:.3f} R={v['recall']:.3f} F1={v['f1']:.3f}")


if __name__ == "__main__":
    main()
