"""เทสต์โครงสร้างเพลงด้วยข้อมูลสังเคราะห์ที่รู้คำตอบ"""
import numpy as np

from melotab.pipeline.structure import bar_features, bar_times, bars_from_beats, detect_key_changes, segment_structure


def beats_4_4(n_bars, pickup=0, bpm=120):
    sec = 60 / bpm
    out = []
    for i in range(pickup + n_bars * 4):
        k = i - pickup
        out.append({"time": i * sec, "beat": 1 if (k >= 0 and k % 4 == 0) else ((k % 4) + 1 if k >= 0 else 4 - (pickup - i) + 1)})
    return out


def test_bars_from_beats_with_and_without_pickup():
    b = beats_4_4(4)
    assert bars_from_beats(b) == [(0, 4), (4, 4), (8, 4), (12, 4)]
    p = beats_4_4(3, pickup=2)
    bars = bars_from_beats(p)
    assert bars[0] == (0, 2) and bars[1][0] == 2 and len(bars) == 4        # ห้อง pickup นับเป็นห้องที่ 1 (เหมือนหน้าแทป)
    assert bars_from_beats([]) == []
    t = bar_times(b, bars_from_beats(b))
    assert t[0] == (0.0, 2.0) and t[-1][1] > t[-1][0]                       # ห้องสุดท้ายยังมีความยาว


def note(midi, t):
    return {"midi": midi, "start": t, "end": t + 0.4}


def test_key_change_detected_when_sustained_but_not_for_relative_or_blip():
    bt = bar_times(beats_4_4(64), bars_from_beats(beats_4_4(64)))
    cmaj = [0, 2, 4, 5, 7, 9, 11]
    dmaj = [2, 4, 6, 7, 9, 11, 1]
    notes = []
    for bar, (t0, t1) in enumerate(bt):
        scale = cmaj if bar < 32 else dmaj                                  # ขึ้นคีย์ที่ห้อง 33 (ขึ้นเต็มเสียง)
        for j in range(8):
            notes.append(note(60 + scale[(bar + j) % 7], t0 + j * 0.25))
    ch = detect_key_changes(notes, bt, {"tonic": "C", "mode": "major"})
    assert len(ch) == 1 and ch[0]["tonic"] == "D" and ch[0]["mode"] == "major"
    assert 28 <= ch[0]["bar"] <= 36                                          # ใกล้ห้องที่ขึ้นคีย์จริง (ความละเอียดตามหน้าต่าง)
    # ไม่มีการเปลี่ยนคีย์เลย → ว่าง
    flat = [note(60 + cmaj[(b + j) % 7], t0 + j * 0.25) for b, (t0, _) in enumerate(bt) for j in range(8)]
    assert detect_key_changes(flat, bt, {"tonic": "C", "mode": "major"}) == []
    # relative minor (A minor ใช้โน้ตชุดเดียวกับ C major) ไม่นับเป็นเปลี่ยนคีย์
    assert detect_key_changes(flat, bt, {"tonic": "A", "mode": "minor"}) == []
    assert detect_key_changes(flat[:5], bt, None) == []


def test_structure_finds_repeated_sections_and_labels_chorus_by_energy():
    # โครง: Intro(4) V(8) C(8) V(8) C(8) Outro(4) — แต่ละกลุ่มมีคอร์ดต่างกัน, Chorus พลังงานสูงกว่า
    def chords_for(kind, start_t, n):
        prog = {"V": [(0, "maj"), (9, "maj"), (4, "min"), (7, "maj")], "C": [(5, "maj"), (0, "maj"), (7, "maj"), (9, "min")],
                "I": [(0, "maj"), (0, "maj"), (0, "maj"), (0, "maj")]}[kind]
        out = []
        for b in range(n):
            root, q = prog[b % 4]
            out.append({"root": root, "quality": q, "start": (start_t + b) * 2.0, "end": (start_t + b + 1) * 2.0})
        return out
    plan = [("I", 4, 0.2), ("V", 8, 0.5), ("C", 8, 0.9), ("V", 8, 0.5), ("C", 8, 0.9), ("I", 4, 0.2)]
    chords, energy, t = [], [], 0
    for kind, n, e in plan:
        chords += chords_for(kind, t, n)
        energy += [e] * n
        t += n
    bt = [(i * 2.0, (i + 1) * 2.0) for i in range(t)]
    F = bar_features(chords, bt, np.array(energy))
    secs = segment_structure(F, np.array(energy), min_bars=4, L=4, sensitivity=0.4)   # ข้อมูลสังเคราะห์มีท่อน 4 ห้อง (ค่าเริ่มต้นจริงคือ 8 ห้อง)
    starts = [s["start_bar"] for s in secs]
    expected = [1, 5, 13, 21, 29, 37]
    assert set(expected) <= set(starts) or len(set(starts) & set(expected)) >= 5, starts   # ขอบท่อนส่วนใหญ่ถูก
    assert secs[0]["start_bar"] == 1 and secs[-1]["end_bar"] == t + 1
    assert all(a["end_bar"] == b["start_bar"] for a, b in zip(secs, secs[1:]))              # ต่อกันพอดี ไม่ทับ/ไม่ขาด
    labels = [s["label"] for s in secs]
    assert any(l.startswith("Chorus") for l in labels), labels
    chorus = [s for s in secs if s["label"].startswith("Chorus")]
    assert all(s["start_bar"] in (13, 29) for s in chorus)                                  # ท่อนที่พลังงานสูงและซ้ำคือ Chorus
    assert labels[0] == "Intro" and labels[-1] == "Outro"
    assert all(s["auto"] for s in secs)


def test_structure_short_song_is_single_section():
    F = np.random.default_rng(0).random((5, 24))
    s = segment_structure(F)
    assert len(s) == 1 and s[0]["start_bar"] == 1 and s[0]["end_bar"] == 6


def test_key_change_ignores_transition_window_and_adjacent_key_confusion():
    """หน้าต่างรอยต่อที่ผสมสองคีย์ต้องไม่ถูกรายงานเป็นคีย์ที่สาม และเพลงที่วนคอร์ด D–A (คีย์ใกล้กัน) ต้องไม่ถูกมองว่าเปลี่ยนคีย์"""
    bt = bar_times(beats_4_4(64), bars_from_beats(beats_4_4(64)))
    cmaj, dmaj = [0, 2, 4, 5, 7, 9, 11], [2, 4, 6, 7, 9, 11, 1]
    notes = [note(60 + (cmaj if b < 32 else dmaj)[(b + j) % 7], t0 + j * 0.25) for b, (t0, _) in enumerate(bt) for j in range(8)]
    ch = detect_key_changes(notes, bt, {"tonic": "C", "mode": "major"})
    assert [(c["tonic"], c["mode"]) for c in ch] == [("D", "major")], ch                  # ไม่มี G ปลอมจากหน้าต่างรอยต่อ
    # เมโลดี้ที่โน้ตกระจายตามโปรไฟล์ของ D major (มีสุ่มรบกวน) ต้องไม่ถูกรายงานว่าเปลี่ยนคีย์
    from melotab.pipeline.key import _MAJOR
    rng = np.random.default_rng(3)
    prof = np.roll(_MAJOR, 2)
    pcs = np.arange(12)
    mixed = []
    for b, (t0, _) in enumerate(bt):
        w = prof * rng.uniform(0.6, 1.4, 12)
        for j, pc in enumerate(rng.choice(pcs, size=16, p=w / w.sum())):
            mixed.append(note(60 + int(pc), t0 + j * 0.125))
    assert detect_key_changes(mixed, bt, {"tonic": "D", "mode": "major"}) == []
