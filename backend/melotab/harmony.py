"""Harmony Line Generator (plan หัวข้อ 22): สร้างไลน์ประสาน diatonic (3rd/6th เหนือหรือใต้เมโลดี้) ในคีย์ของเพลง สำหรับ twin guitar/อัดซ้อน

กติกา: ขยับตามขั้นของสเกลคีย์หลัก (major/minor ธรรมชาติ) ไม่ใช่ครึ่งเสียงคงที่ → ได้ 3rd เมเจอร์/ไมเนอร์ตามบันไดเสียงเอง
ถ้ามีคอร์ด และ `prefer_chord_tone` เปิด: ลองทางเลือก 3rd/6th ที่ทิศเดียวกันแล้วเลือกตัวที่เป็นโน้ตของคอร์ดในจังหวะนั้น (ไม่มี = ใช้ interval ที่ขอ)
ข้อจำกัด: ไม่ดู key change กลางเพลง, ไม่เลี่ยงช่วงเสียงชนกับเมโลดี้ (unison/ขนาน octave) เกินกว่ากฎข้างต้น, ไม่ได้ฟังตรวจกับเพลงจริง
"""
from __future__ import annotations

from .pipeline.chords import QUALITY
from .tab.theory import MAJOR, MINOR, NOTE_NAMES

STEPS = {"third": 2, "sixth": 5}


def _scale_midis(tonic_pc: int, mode: str, lo: int = 20, hi: int = 110) -> list[int]:
    ivs = MINOR if mode == "minor" else MAJOR
    pcs = {(tonic_pc + i) % 12 for i in ivs}
    return [m for m in range(lo, hi) if m % 12 in pcs]


def _chord_pcs(chords: list[dict], t: float) -> set[int] | None:
    for c in chords:
        if c["start"] <= t < c["end"] and c.get("root") is not None and c.get("quality") in QUALITY:
            return {(c["root"] + i) % 12 for i in QUALITY[c["quality"]][1]}
    return None


def generate(notes: list[dict], key: dict, chords: list[dict] | None = None, *, interval: str = "third", direction: str = "above",
             prefer_chord_tone: bool = True) -> list[dict]:
    if interval not in STEPS or direction not in ("above", "below"):
        raise ValueError("interval ต้องเป็น third|sixth และ direction เป็น above|below")
    if not key:
        raise ValueError("ไม่มีคีย์ของเพลง")
    tonic = NOTE_NAMES.index(key["tonic"])
    scale = _scale_midis(tonic, key["mode"])
    sgn = 1 if direction == "above" else -1
    out = []
    for n in notes:
        # ตำแหน่งในสเกล (ถ้าโน้ตนอกสเกล ใช้ขั้นที่ใกล้ที่สุดด้านล่าง)
        idx = max((i for i, m in enumerate(scale) if m <= n["midi"]), default=0)
        cands = [interval] + ([k for k in STEPS if k != interval] if prefer_chord_tone else [])
        pick = scale[min(max(idx + sgn * STEPS[interval], 0), len(scale) - 1)]
        if prefer_chord_tone and chords:
            cp = _chord_pcs(chords, n["start"])
            if cp:
                for k in cands:
                    m = scale[min(max(idx + sgn * STEPS[k], 0), len(scale) - 1)]
                    if m % 12 in cp:
                        pick = m
                        break
        out.append({**{k: v for k, v in n.items() if k in ("start", "end", "start_beat", "dur_beats", "start_beat_q", "dur_beats_q", "confidence")},
                    "id": f"h_{n['id']}", "midi": int(pick), "name": NOTE_NAMES[pick % 12] + str(pick // 12 - 1), "source_note": n["id"]})
    return out
