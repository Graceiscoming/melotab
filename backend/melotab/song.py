"""ประกอบ Song Model (song.json, plan หัวข้อ 19 เวอร์ชันย่อของ Phase 1) และ export MIDI"""
import json
from pathlib import Path

import mido
import numpy as np


def _beat_positions(notes: list[dict], beats: list[dict]) -> None:
    """เติม start_beat / dur_beats (นับ beat จาก beat แรก = 0) โดย interpolate ตามเวลาของ beat grid จริง"""
    if len(beats) < 2:
        return
    bt = np.array([b["time"] for b in beats])
    idx = np.arange(len(bt), dtype=float)
    ibi0, ibi1 = bt[1] - bt[0], bt[-1] - bt[-2]

    def pos(t: float) -> float:
        if t < bt[0]:
            return float((t - bt[0]) / ibi0)
        if t > bt[-1]:
            return float(idx[-1] + (t - bt[-1]) / ibi1)
        return float(np.interp(t, bt, idx))

    for n in notes:
        s, e = pos(n["start"]), pos(n["end"])
        n["start_beat"], n["dur_beats"] = round(s, 3), round(e - s, 3)


def build_song(*, source: dict, notes: list[dict], rhythm: dict, key: dict | None,
               f0_ref: str | None, meta: dict) -> dict:
    _beat_positions(notes, rhythm.get("beats", []))
    return {
        "version": 1,
        "source": source,
        "key": key,
        "tempo": {"bpm": rhythm.get("bpm"), "bpm_raw_median": rhythm.get("bpm_raw_median"),
                  "unstable": rhythm.get("tempo_unstable")},
        "time_signature": rhythm.get("time_signature"),
        "beats": rhythm.get("beats", []),
        "notes": notes,
        "f0_ref": f0_ref,
        "meta": meta,
    }


def save_song(song: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(song, ensure_ascii=False, indent=1), encoding="utf-8")


def export_midi(notes: list[dict], path: Path, bpm: float = 120.0, ppq: int = 480) -> None:
    """MIDI ที่เวลาเป็นเวลาจริง (วินาที) ที่ tempo คงที่ — ยังไม่ผูกกับ beat grid"""
    mid = mido.MidiFile(ticks_per_beat=ppq)
    track = mido.MidiTrack()
    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm), time=0))
    ticks_per_s = ppq * bpm / 60.0
    events = []
    for n in notes:
        events.append((round(n["start"] * ticks_per_s), 1, n["midi"]))
        events.append((round(n["end"] * ticks_per_s), 0, n["midi"]))
    events.sort()
    last = 0
    for t, on, midi in events:
        track.append(mido.Message("note_on" if on else "note_off", note=int(midi), velocity=90 if on else 0, time=t - last))
        last = t
    mid.tracks.append(track)
    path.parent.mkdir(parents=True, exist_ok=True)
    mid.save(path)
