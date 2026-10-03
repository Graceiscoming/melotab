"""เทสต์ส่วนที่ไม่ต้องใช้ GPU/โมเดล: key, ตำแหน่ง beat, export MIDI, annotate confidence"""
import mido
import numpy as np

from melotab.pipeline.key import estimate_key
from melotab.pipeline.notes import annotate, estimate_tuning, refine
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
    out = annotate([_n(69, 0.0, 1.0), _n(57, 1.0, 2.0)], f0, fix_octave=False)    # ตัวที่ 2 ต่ำกว่า 1 octave
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


def test_octave_auto_fix_moves_note_and_flags_it():
    times = np.arange(0, 2, 0.01, dtype=np.float32)
    f0 = {"times": times, "f0_hz": np.full_like(times, 440.0)}
    out = annotate([_n(57, 0.0, 1.0)], f0)                  # SOME ได้ A3 แต่ f0 = A4
    assert out[0]["midi"] == 69 and out[0]["name"] == "A4"
    assert out[0]["octave_fixed"] and not out[0]["octave_suspect"]
    assert out[0]["confidence"] <= 0.6                       # ผ่านการแก้อัตโนมัติ ควรให้คนตรวจ


def test_octave_fix_leaves_non_octave_difference_alone():
    times = np.arange(0, 2, 0.01, dtype=np.float32)
    f0 = {"times": times, "f0_hz": np.full_like(times, 440.0)}
    out = annotate([_n(50, 0.0, 1.0)], f0)                  # ต่าง 19 semitone ไม่ใช่พหุคูณ 12 → ไม่แตะ
    assert out[0]["midi"] == 50 and out[0]["octave_suspect"] and not out[0]["octave_fixed"]


def test_estimate_tuning_detects_offset():
    hz = 440.0 * 2 ** (-30 / 1200) * 2 ** (np.random.default_rng(0).integers(-12, 12, 3000) / 12)   # ต่ำกว่า 440 อยู่ 30 cents
    est = estimate_tuning({"f0_hz": hz.astype(np.float32)})
    assert -34 <= est <= -26
    assert estimate_tuning({"f0_hz": np.zeros(10, dtype=np.float32)}) == 0.0


def test_refine_merges_same_pitch_and_drops_short():
    raw = [_n(60, 0.0, 0.3), _n(60, 0.32, 0.6), _n(62, 0.7, 0.75), _n(64, 1.0, 1.5)]
    out = refine(raw, min_dur_ms=100, merge_gap_ms=50)
    assert [(n["midi"], n["start"], n["end"]) for n in out] == [(60, 0.0, 0.6), (64, 1.0, 1.5)]
    assert len(refine(raw)) == 4                              # ค่าเริ่มต้นไม่แตะอะไร


def test_quantize_keeps_real_time_and_snaps_beats():
    beats = [{"time": float(t)} for t in range(10)]          # 60 BPM
    notes = [{"start": 1.1, "end": 1.9}]
    _beat_positions(notes, beats)
    assert notes[0]["start_beat"] == 1.1                      # เวลาจริงไม่ถูกแตะ
    assert notes[0]["start_beat_q"] == 1.0 and notes[0]["dur_beats_q"] == 1.0


def test_refine_default_never_merges_repeated_notes():
    """ร้องโน้ตเดิมซ้ำติดกันพอดี (ช่องว่าง 0) ต้องเป็นสองโน้ตเสมอเมื่อไม่ได้ตั้ง merge_gap — บั๊กที่เคยทำโน้ตหาย ~22%"""
    raw = [_n(60, 0.0, 0.5), _n(60, 0.5, 1.0)]
    assert len(refine(raw)) == 2
    assert len(refine(raw, merge_gap_ms=0)) == 2
    assert len(refine(raw, merge_gap_ms=20)) == 1
