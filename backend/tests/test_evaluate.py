"""ทดสอบฟังก์ชันประเมินด้วยข้อมูลสังเคราะห์ที่รู้คำตอบ"""
import numpy as np

from melotab.evaluate import evaluate_f0, evaluate_notes, load_notes
from melotab.song import export_midi


def _notes(spec):
    iv = np.array([[a, b] for a, b, _ in spec], dtype=float)
    hz = np.array([440.0 * 2 ** ((m - 69) / 12) for *_, m in spec], dtype=float)
    return iv, hz


REF = [(0.0, 0.5, 60), (0.5, 1.0, 62), (1.0, 1.5, 64), (1.5, 2.0, 65)]


def test_perfect_match_is_f1_one():
    r = evaluate_notes(_notes(REF), _notes(REF))
    assert r["COnP"]["f1"] == 1.0 and r["COnPOff"]["f1"] == 1.0


def test_wrong_pitch_and_wrong_onset_are_penalised():
    est = [(0.0, 0.5, 60), (0.5, 1.0, 63), (1.3, 1.8, 64), (1.5, 2.0, 65)]   # ตัวที่ 2 ผิด pitch, ตัวที่ 3 onset ช้า 300 ms
    r = evaluate_notes(_notes(REF), _notes(est))
    assert abs(r["COnP"]["f1"] - 0.5) < 1e-9 and r["n_ref"] == 4 and r["n_est"] == 4


def test_empty_prediction_is_zero_not_crash():
    r = evaluate_notes(_notes(REF), (np.zeros((0, 2)), np.zeros(0)))
    assert r["COnP"]["f1"] == 0.0


def test_midi_roundtrip_through_loader(tmp_path):
    p = tmp_path / "x.mid"
    export_midi([{"midi": m, "start": a, "end": b} for a, b, m in REF], p)
    r = evaluate_notes(_notes(REF), load_notes(p))
    assert r["COnP"]["f1"] == 1.0


def test_f0_octave_error_hurts_rpa_but_not_rca():
    t = np.arange(0, 2, 0.01)
    ref = np.full_like(t, 440.0)
    est = ref.copy(); est[100:] = 220.0                       # ครึ่งหลังผิดไป 1 octave
    r = evaluate_f0(t, ref, t, est)
    assert 0.45 < r["RPA"] < 0.55 and r["RCA"] > 0.99
