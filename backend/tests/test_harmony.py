import pytest

from melotab.harmony import generate

KEY = {"tonic": "C", "mode": "major"}


def N(i, m):
    return {"id": f"n{i}", "midi": m, "start": i * 0.5, "end": i * 0.5 + 0.4}


def test_diatonic_thirds_above_in_c_major():
    notes = [N(i, m) for i, m in enumerate([60, 62, 64, 65, 67, 69, 71, 72])]
    h = generate(notes, KEY, interval="third", prefer_chord_tone=False)
    assert [x["midi"] for x in h] == [64, 65, 67, 69, 71, 72, 74, 76]          # 3rd เมเจอร์/ไมเนอร์ตามสเกล
    assert all(x["midi"] % 12 in {0, 2, 4, 5, 7, 9, 11} for x in h)
    assert h[0]["source_note"] == "n0" and h[0]["start"] == notes[0]["start"]


def test_sixth_below_and_minor_key():
    assert [x["midi"] for x in generate([N(0, 72)], KEY, interval="sixth", direction="below", prefer_chord_tone=False)] == [64]
    a_min = {"tonic": "A", "mode": "minor"}
    assert generate([N(0, 69)], a_min, interval="third", prefer_chord_tone=False)[0]["midi"] == 72      # A→C (3rd ไมเนอร์)


def test_prefers_chord_tone():
    chords = [{"start": 0.0, "end": 9.0, "root": 0, "quality": "maj"}]                                   # C major: C E G
    h = generate([N(0, 62)], KEY, chords, interval="third", direction="above")                           # D+3rd = F (ไม่ใช่โน้ตคอร์ด) → ลอง 6th = B (ไม่ใช่) → คงตามที่ขอ
    assert h[0]["midi"] == 65
    h2 = generate([N(0, 64)], KEY, chords, interval="third", direction="above")                          # E→G เป็นโน้ตคอร์ด
    assert h2[0]["midi"] == 67
    h3 = generate([N(0, 67)], KEY, chords, interval="third", direction="above")                          # G→B ไม่ใช่ → 6th เหนือ G = E เป็นโน้ตคอร์ด
    assert h3[0]["midi"] == 76


def test_errors():
    with pytest.raises(ValueError):
        generate([N(0, 60)], None)
    with pytest.raises(ValueError):
        generate([N(0, 60)], KEY, interval="fifth")
