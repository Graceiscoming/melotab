"""Export MIDI (.mid): แทรกเมโลดี้ (+ แทรกคอร์ดถ้าต้องการ) — ใช้ pretty_midi"""
from __future__ import annotations

from pathlib import Path

import pretty_midi

from ..pipeline.chords import QUALITY
from .model import beat_to_time


def write_midi(song: dict, path: Path, *, quantized: bool = False, with_chords: bool = True) -> dict:
    bpm = float((song.get("tempo") or {}).get("bpm") or 120.0)
    pm = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    beats = song.get("beats") or []
    spb = 60.0 / bpm

    def tq(beat: float) -> float:                                  # ตำแหน่งแบบ "ปัดตามกริด": beat × ความยาวคงที่ (เริ่มที่ beat แรก)
        return (beats[0]["time"] if beats else 0.0) + beat * spb

    mel = pretty_midi.Instrument(program=29, name="Melody")        # 29 = overdriven guitar (เมโลดี้)
    n_notes = 0
    for n in sorted(song.get("notes", []), key=lambda x: x["start"]):
        if quantized and n.get("start_beat_q") is not None:
            a = tq(n["start_beat_q"])
            b = tq(n["start_beat_q"] + max(0.25, n.get("dur_beats_q") or n.get("dur_beats") or 0.25))
        else:
            a, b = n["start"], n["end"]
        if b <= a:
            b = a + 0.05
        mel.notes.append(pretty_midi.Note(velocity=int(60 + 50 * min(1.0, n.get("confidence", 0.7))), pitch=int(n["midi"]), start=a, end=b))
        n_notes += 1
    pm.instruments.append(mel)

    n_chords = 0
    if with_chords and song.get("chords"):
        ch = pretty_midi.Instrument(program=24, name="Chords")
        for c in song["chords"]:
            if c.get("root") is None or c.get("quality") not in QUALITY:
                continue
            a = c["start"] if not quantized else tq(c["start_beat"])
            b = c["end"] if not quantized else tq(c["end_beat"])
            for iv in QUALITY[c["quality"]][1]:
                ch.notes.append(pretty_midi.Note(velocity=55, pitch=48 + (c["root"] + iv) % 12 + (12 if (c["root"] + iv) % 12 < c["root"] % 12 else 0), start=a, end=max(b, a + 0.1)))
            n_chords += 1
        pm.instruments.append(ch)
    path.parent.mkdir(parents=True, exist_ok=True)
    pm.write(str(path))
    return {"notes": n_notes, "chords": n_chords}


_ = beat_to_time  # (เผื่อใช้ต่อ)
