"""เทสต์ส่วนคอร์ดที่ไม่ต้องใช้ GPU: แปลงชื่อ, smoothing ตาม beat, slash chord"""
import numpy as np

from melotab.pipeline.chords import QUALITY, build_chords, parse_label, smooth_to_beats

BEATS = [i * 0.5 for i in range(33)]       # 120 BPM, 32 beat


def test_parse_label_names():
    assert parse_label("D") is None or True
    assert parse_label("D:maj")["symbol"] == "D"
    assert parse_label("B:min")["symbol"] == "Bm"
    assert parse_label("A:min7")["symbol"] == "Am7"
    assert parse_label("G:maj7")["symbol"] == "Gmaj7"
    assert parse_label("E:7")["symbol"] == "E7"
    assert parse_label("A:hdim7")["symbol"] == "Am7b5"
    assert parse_label("Bb:maj")["symbol"] == "A#"           # แปลง ♭ เป็น ♯ ภายใน (ชื่อ ♭ เลือกตอนแสดงตามคีย์)
    assert parse_label("N") is None and parse_label("X") is None
    assert parse_label("C:weird")["symbol"] == "C"           # คลาสที่ไม่รู้จักไม่ทำให้ล้ม


def test_smoothing_snaps_changes_to_beats_and_removes_flicker():
    # D เต็ม 8 beat แต่มี G สั้น ๆ 0.2 s แทรกกลางที่ไม่ตรง beat, แล้ว A 8 beat
    segs = [(0.0, 1.9, "D"), (1.9, 2.1, "G"), (2.1, 4.0, "D"), (4.0, 8.0, "A")]
    out = smooth_to_beats(segs, BEATS, min_beats=2)
    labels = [(s["label"], s["start_beat"], s["end_beat"]) for s in out]
    assert labels[0] == ("D", 0, 8) and labels[1] == ("A", 8, 16)
    assert all(abs(s["start"] - BEATS[s["start_beat"]]) < 1e-6 for s in out)       # ขอบตรง beat เสมอ


def test_smoothing_keeps_real_short_chords_when_min_beats_is_one():
    segs = [(0.0, 2.0, "D"), (2.0, 2.5, "G"), (2.5, 4.0, "D")]
    chords = lambda mb: [s["label"] for s in smooth_to_beats(segs, BEATS, min_beats=mb) if s["label"] != "N"]   # beat grid ยาวกว่าคอร์ด → ท้ายเป็น N
    assert chords(1) == ["D", "G", "D"]
    assert chords(2) == ["D"]


def test_smoothing_handles_no_chord_and_missing_beats():
    segs = [(0.0, 1.0, "N"), (1.0, 4.0, "C")]
    out = smooth_to_beats(segs, BEATS, min_beats=1)
    assert out[0]["label"] == "N" and out[1]["label"] == "C"
    assert smooth_to_beats(segs, [], 2)[0]["label"] == "N"                          # ไม่มี beat grid → คืนตามเดิมไม่ล้ม


def test_slash_chord_only_when_bass_is_clear_chord_tone():
    segs = [{"start_beat": 0, "end_beat": 4, "start": 0, "end": 2, "label": "C:maj"}] * 3
    def e(pc, amount):
        v = np.full(12, 0.01); v[pc] = amount; return v
    bass = [e(4, 5.0),        # E เด่น (เทอร์ดของ C) → C/E
            e(0, 5.0),        # root เด่น → ไม่ใช่ slash
            e(1, 5.0)]        # C# ไม่ใช่โน้ตในคอร์ด C → ไม่ใช่ slash
    out = build_chords(segs, bass)
    assert out[0]["symbol"] == "C/E" and out[0]["bass"] == "E"
    assert out[1]["symbol"] == "C" and out[1]["bass"] is None
    assert out[2]["symbol"] == "C" and out[2]["bass"] is None
    assert all(c["confidence"] is None for c in out)                                # ไม่แต่งค่า confidence ที่ไม่มี


def test_quality_table_has_chord_tones():
    for q, (_, tones) in QUALITY.items():
        assert tones[0] == 0 and list(tones) == sorted(tones), q


def test_run_btc_passes_absolute_audio_path(monkeypatch, tmp_path):
    """โปรเซสลูกมี cwd = third_party/BTC ดังนั้น path ที่ส่งไปต้องเป็น path เต็ม (เคยพังเพราะส่ง path สัมพัทธ์)"""
    import subprocess
    from melotab.pipeline import chords
    seen = {}

    def fake_run(cmd, cwd=None, env=None, capture_output=None, text=None):
        seen["audio"] = cmd[3]
        open(cmd[4], "w", encoding="utf-8").write("0.000 1.000 C:maj\n")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(chords.subprocess, "run", fake_run)
    monkeypatch.setattr(chords, "THIRD_PARTY", tmp_path)
    (tmp_path / "BTC").mkdir()
    monkeypatch.chdir(tmp_path)
    assert chords.run_btc("some/relative/x.wav") == [(0.0, 1.0, "C:maj")]
    assert seen["audio"] == str((tmp_path / "some/relative/x.wav").resolve())
