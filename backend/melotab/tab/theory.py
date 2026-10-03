"""ทฤษฎีกีตาร์: tuning, ตำแหน่ง (สาย, ช่อง) ที่เล่นโน้ตได้, สเกล

เลขสาย: 1 = สายบางสุด (สูงสุด) … 6 = สายหนาสุด (ต่ำสุด) ตามแทปทั่วไป
เลขช่อง: นับจาก capo (ช่อง 0 = สายเปล่าเมื่อไม่มี capo / ตัว capo เมื่อมี capo) — พิทช์ของช่อง f = open + capo + f
"""
from __future__ import annotations

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# MIDI ของสายเปล่า เรียงจากสาย 6 → สาย 1 (ต่ำ → สูง) เป็น "เสียงจริง" (E2 = 40)
TUNINGS: dict[str, list[int]] = {
    "standard": [40, 45, 50, 55, 59, 64],       # E A D G B E
    "eb": [39, 44, 49, 54, 58, 63],              # ต่ำลงครึ่งเสียง (Eb standard)
    "drop_d": [38, 45, 50, 55, 59, 64],          # D A D G B E
    "dadgad": [38, 45, 50, 55, 57, 62],
}
MAX_FRET_DEFAULT = 22

MAJOR = [0, 2, 4, 5, 7, 9, 11]
MINOR = [0, 2, 3, 5, 7, 8, 10]
MAJOR_PENT = [0, 2, 4, 7, 9]
MINOR_PENT = [0, 3, 5, 7, 10]


def pc_of(name: str) -> int:
    return NOTE_NAMES.index(name)


def scale_pcs(tonic: str, mode: str, pentatonic: bool = False) -> set[int]:
    t = pc_of(tonic)
    steps = (MINOR_PENT if mode == "minor" else MAJOR_PENT) if pentatonic else (MINOR if mode == "minor" else MAJOR)
    return {(t + s) % 12 for s in steps}


def open_pitches(tuning: list[int], capo: int = 0) -> list[int]:
    """พิทช์ของ 'ช่อง 0' ของแต่ละสาย (เรียงสาย 6→1) หลังติด capo"""
    return [p + capo for p in tuning]


def positions_for(pitch: int, tuning: list[int], capo: int = 0, max_fret: int = MAX_FRET_DEFAULT) -> list[tuple[int, int]]:
    """คืน [(string, fret)] ทั้งหมดที่เล่น pitch ได้ (string 1..6) เรียงจากสายบาง→หนา; max_fret = ช่องสูงสุดที่นับจาก capo"""
    out = []
    for i, base in enumerate(open_pitches(tuning, capo)):
        f = pitch - base
        if 0 <= f <= max_fret:
            out.append((6 - i, f))              # i=0 คือสาย 6
    return sorted(out)


def pitch_at(string: int, fret: int, tuning: list[int], capo: int = 0) -> int:
    return tuning[6 - string] + capo + fret
