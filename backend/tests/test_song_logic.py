"""เทสต์ส่วนที่ไม่ต้องใช้ GPU/โมเดล: key, ตำแหน่ง beat, export MIDI, annotate confidence"""
import mido
import numpy as np

from melotab.pipeline.key import estimate_key
from melotab.pipeline.notes import annotate
from melotab.song import _beat_positions, export_midi


def _n(midi, s, e):
    return {"midi": midi, "start": s, "end": e}


def test_key_c_major_scale():
    notes = [_n(m, i, i + 1) for i, m in enumerate([60, 62, 64, 65, 67, 69, 71, 60, 64, 67])]
    k = estimate_key(notes)
    assert (k["tonic"], k["mode"]) == ("C", "major")


def test_key_empty():
    assert estimate_key([]) is None


def test_beat_positions_interpolates_with_tempo_change():
    beats = [{"time": t} for t in (0.0, 1.0, 2.0, 2.5, 3.0)]   # ช่วงท้าย tempo เร็วขึ้นเท่าตัว
    notes = [{"start": 0.5, "end": 2.25}]
    _beat_positions(notes, beats)
    assert notes[0]["start_beat"] == 0.5
    assert abs(notes[0]["dur_beats"] - 2.0) < 1e-6


def test_annotate_confidence_and_octave_flag():
    times = np.arange(0, 3, 0.01, dtype=np.float32)
    hz = np.full_like(times, 440.0)            # A4 = MIDI 69 ตลอด
    f0 = {"times": times, "f0_hz": hz}
    out = annotate([_n(69, 0.0, 1.0), _n(57, 1.0, 2.0)], f0)    # ตัวที่ 2 ต่ำกว่า 1 octave
    assert out[0]["name"] == "A4" and out[0]["confidence"] > 0.9 and not out[0]["octave_suspect"]
    assert out[1]["octave_suspect"]
    assert out[1]["confidence"] <= 0.1 + 1e-9 and out[1]["cents_offset"] is None


def test_annotate_unvoiced_gets_low_confidence():
    times = np.arange(0, 2, 0.01, dtype=np.float32)
    out = annotate([_n(60, 0.0, 1.0)], {"times": times, "f0_hz": np.zeros_like(times)})
    assert out[0]["confidence"] == 0.2 and out[0]["cents_offset"] is None


def test_export_midi_roundtrip(tmp_path):
    p = tmp_path / "m.mid"
    export_midi([_n(60, 0.0, 0.5), _n(64, 0.5, 1.0)], p)
    t = 0.0
    on = []
    for m in mido.MidiFile(p):
        t += m.time
        if m.type == "note_on" and m.velocity > 0:
            on.append((m.note, round(t, 3)))
    assert on == [(60, 0.0), (64, 0.5)]
