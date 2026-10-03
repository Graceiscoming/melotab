"""Block Mode: จำกัดโซนบนคอกีตาร์ (plan หัวข้อ 11)

Block = หน้าต่างช่อง [fret_min, fret_max] ทุกสาย + เซตโน้ตของสเกลที่ใช้แสดงจุดบน fretboard
ระบบที่รองรับตอนนี้:
  - "position": 7 ตำแหน่งตามองศาสเกลบนสาย 6 (หน้าต่าง 5 ช่อง) — แนวเดียวกับระบบ 3-notes-per-string
  - "pentatonic": 5 box ของเพนทาโทนิก
  - "custom": ผู้ใช้กำหนดช่วงช่องเอง
ยังไม่มี CAGED แท้ (ต้องใช้ทรงคอร์ดเป็นฐาน ยังไม่ได้ทำ) และยังไม่มี block แยกตามท่อนเพลง (ต้องรอ section จาก Phase 4)
เลขช่องเป็นเลขที่ผู้ใช้เห็น (นับจาก capo)
"""
from __future__ import annotations

from .theory import MAX_FRET_DEFAULT, open_pitches, scale_pcs

WINDOW = 5      # ความกว้างหน้าต่าง (ช่อง) มาตรฐานของ 1 ตำแหน่ง


def generate_blocks(tonic: str, mode: str, tuning: list[int], capo: int = 0, system: str = "position",
                    max_fret: int = MAX_FRET_DEFAULT) -> list[dict]:
    """tonic/mode คือคีย์ของ "เสียงที่เล่นจริง" (หลัง transpose)"""
    pent = system == "pentatonic"
    pcs = scale_pcs(tonic, mode, pentatonic=pent)
    low = open_pitches(tuning, capo)[0]                        # พิทช์ช่อง 0 ของสายต่ำสุด
    starts = [f for f in range(0, max_fret + 1) if (low + f) % 12 in pcs]
    # หนึ่งรอบ octave ต่อ 1 block; ตัดตำแหน่งที่ window ล้นเกินคอ
    blocks, seen = [], set()
    for f in starts:
        lo, hi = max(0, f - 1), f + WINDOW - 2                 # นิ้วชี้เอื้อมถอยหลังได้ 1 ช่อง
        if hi > max_fret:
            continue
        key = (lo, hi)
        if key in seen:
            continue
        seen.add(key)
        blocks.append({"fret_min": lo, "fret_max": hi, "system": system, "pcs": sorted(pcs)})
    blocks.sort(key=lambda b: b["fret_min"])
    label = "Pentatonic Box" if pent else "ตำแหน่ง"
    for i, b in enumerate(blocks, 1):
        b["id"] = f"{system}{i}"
        b["label"] = f"{label} {i} (ช่อง {b['fret_min']}–{b['fret_max']})"
    return blocks


def custom_block(fret_min: int, fret_max: int, bid: str = "custom1") -> dict:
    if fret_min > fret_max:
        fret_min, fret_max = fret_max, fret_min
    return {"id": bid, "label": f"Custom (ช่อง {fret_min}–{fret_max})", "system": "custom",
            "fret_min": fret_min, "fret_max": fret_max, "pcs": []}


def coverage(notes_pitches: list[int], blocks: list[dict], tuning: list[int], capo: int = 0) -> float:
    """สัดส่วนโน้ตที่เล่นได้ภายใน block อย่างน้อยหนึ่งตำแหน่ง (แสดง preview ก่อนสร้างแทป)"""
    from .theory import positions_for
    if not notes_pitches or not blocks:
        return 0.0
    ok = 0
    for p in notes_pitches:
        pos = positions_for(p, tuning, capo)
        if any(b["fret_min"] <= f <= b["fret_max"] for _, f in pos for b in blocks):
            ok += 1
    return ok / len(notes_pitches)
