"""ประมาณคีย์จากโน้ตเมโลดี้ที่แกะได้ (Krumhansl-Schmuckler) — แบบง่าย ใช้เมโลดี้อย่างเดียว

Phase 1 ยังไม่ใช้ chroma/คอร์ด/key change ตาม plan หัวข้อ 6 ขั้น [4] (ทำใน Phase 4) ค่า `score` คือสหสัมพันธ์ ไม่ใช่ความน่าจะเป็น
"""
import numpy as np

_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def estimate_key(notes: list[dict]) -> dict | None:
    if not notes:
        return None
    hist = np.zeros(12)
    for n in notes:
        hist[n["midi"] % 12] += n["end"] - n["start"]
    if hist.sum() == 0:
        return None
    cands = []
    for tonic in range(12):
        for mode, prof in (("major", _MAJOR), ("minor", _MINOR)):
            score = float(np.corrcoef(hist, np.roll(prof, tonic))[0, 1])
            cands.append((score, _NAMES[tonic], mode))
    cands.sort(reverse=True)
    best = cands[0]
    return {"tonic": best[1], "mode": best[2], "score": round(best[0], 3),
            "alternatives": [{"tonic": t, "mode": m, "score": round(s, 3)} for s, t, m in cands[1:4]]}


def key_scores(notes: list[dict]) -> dict[tuple[str, str], float]:
    """สหสัมพันธ์ของฮิสโทแกรมโน้ต (ถ่วงตามความยาว) กับทุกคีย์ (24 คีย์) — ใช้เทียบคีย์ปัจจุบันกับคีย์ที่น่าจะเปลี่ยนไป"""
    hist = np.zeros(12)
    for n in notes:
        hist[n["midi"] % 12] += n["end"] - n["start"]
    if hist.sum() == 0 or np.ptp(hist) == 0:
        return {}
    return {(_NAMES[t], mode): float(np.corrcoef(hist, np.roll(prof, t))[0, 1])
            for t in range(12) for mode, prof in (("major", _MAJOR), ("minor", _MINOR))}
