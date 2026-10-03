"""แกะโน้ตใหม่ด้วย sensitivity/ตัวเลือกใหม่ โดยใช้ผลดิบของ SOME + f0 ที่เก็บไว้ในโปรเจกต์ (ไม่รันโมเดลซ้ำ → เร็ว)

ข้อควรระวัง: โน้ตที่ผู้ใช้แก้ไว้ (edited) จะถูกแทนที่ทั้งหมด — UI ต้องเตือนก่อนเรียก
"""
import json
from pathlib import Path

import numpy as np

from .pipeline import key as key_stage
from .pipeline import notes as notes_stage
from .song import _beat_positions, export_midi, save_song


def retranscribe(project_dir: Path, *, fix_octave: bool = True, min_dur_ms: float = 0.0, merge_gap_ms: float = 0.0) -> dict:
    song = json.loads((project_dir / "song.json").read_text(encoding="utf-8"))
    raw_f = project_dir / "analysis" / "notes_raw.json"
    f0_f = project_dir / "analysis" / "f0.npz"
    if not raw_f.exists() or not f0_f.exists():
        raise FileNotFoundError("ไม่มีผลดิบของการแกะโน้ต — ต้องวิเคราะห์โปรเจกต์นี้ใหม่ก่อน")
    z = np.load(f0_f)
    f0 = {"f0_hz": z["f0_hz"], "times": z["times"], "hop_s": float(z["hop_s"])}
    raw = json.loads(raw_f.read_text(encoding="utf-8"))
    tuning = notes_stage.estimate_tuning(f0)
    notes = notes_stage.annotate(notes_stage.refine(raw, min_dur_ms=min_dur_ms, merge_gap_ms=merge_gap_ms), f0,
                                 fix_octave=fix_octave, tuning_cents=tuning)
    _beat_positions(notes, song.get("beats", []))
    song.update(notes=notes, key=key_stage.estimate_key(notes), tuning_offset_cents=tuning)
    song["meta"].update(fix_octave=fix_octave, min_dur_ms=min_dur_ms, merge_gap_ms=merge_gap_ms)
    save_song(song, project_dir / "song.json")
    export_midi(notes, project_dir / "melody.mid")
    return song
