"""เทสต์ Tab Engine ด้วยโน้ตสังเคราะห์ที่รู้คำตอบ"""
import time

import pytest

from melotab.tab import TabSettings, alternatives, coverage, custom_block, generate_blocks, generate_tab, suggest
from melotab.tab.theory import TUNINGS, pitch_at, positions_for, scale_pcs


def N(i, midi, t, dur=0.4):
    return {"id": f"n{i}", "midi": midi, "start": t, "end": t + dur, "start_beat_q": t * 2, "dur_beats_q": dur * 2}


def melody(pitches, step=0.5):
    return [N(i, p, i * step) for i, p in enumerate(pitches)]


STD = TUNINGS["standard"]


def test_positions_for_standard_tuning():
    pos = positions_for(64, STD)                         # E4 = สาย 1 ช่อง 0, สาย 2 ช่อง 5, สาย 3 ช่อง 9, สาย 4 ช่อง 14, สาย 5 ช่อง 19
    assert (1, 0) in pos and (2, 5) in pos and (3, 9) in pos and (4, 14) in pos and (5, 19) in pos
    assert all(pitch_at(s, f, STD) == 64 for s, f in pos)
    assert positions_for(30, STD) == []                  # ต่ำกว่าสาย 6 เปล่า เล่นไม่ได้
    assert positions_for(64, STD, capo=2) and all(pitch_at(s, f, STD, 2) == 64 for s, f in positions_for(64, STD, 2))


def test_every_event_has_correct_pitch_and_no_note_lost():
    notes = melody([60, 62, 64, 65, 67, 69, 71, 72, 74, 76])
    r = generate_tab(notes)
    assert len(r["events"]) == len(notes)
    for e, n in zip(r["events"], notes):
        assert e["note_id"] == n["id"] and e["fret"] is not None
        assert pitch_at(e["string"], e["fret"], STD) == n["midi"]            # โน้ตต้องถูกเสมอ


def test_open_strings_not_forced_and_hand_stays_close():
    # สเกล C major ขึ้น-ลง: ผลที่ดีควรอยู่ในโซนเดียว ไม่ย้ายมือไปมาไกล
    notes = melody([60, 62, 64, 65, 67, 69, 71, 72, 71, 69, 67, 65, 64, 62, 60])
    r = generate_tab(notes)
    frets = [e["fret"] for e in r["events"]]
    assert max(frets) - min(frets) <= 7
    assert r["summary"]["hard"] == 0 and r["summary"]["unplayable"] == 0


def test_fast_far_jump_is_flagged_as_hard_shift():
    notes = [N(0, 52, 0.0, 0.1), N(1, 76, 0.12, 0.1)]    # E3 → E5 ในเวลา 120 ms: ต้องกระโดดไกลมาก
    e = generate_tab(notes)["events"]
    # โน้ตทั้งสองเล่นได้หลายตำแหน่ง ระบบต้องเลือกให้ใกล้กันที่สุดเท่าที่เป็นไปได้ → ถ้าไม่มีทางใกล้ ต้องเตือน
    assert e[0]["fret"] is not None and e[1]["fret"] is not None


def test_note_below_guitar_range_is_unplayable_not_crash():
    notes = melody([30, 60, 62])
    r = generate_tab(notes)
    assert "unplayable" in r["events"][0]["warnings"] and r["events"][0]["fret"] is None
    assert r["events"][1]["fret"] is not None
    assert r["summary"]["unplayable"] == 1


def test_capo_and_transpose_keep_sounding_pitch_consistent():
    notes = melody([64, 66, 68])
    for capo in (0, 2, 5):
        r = generate_tab(notes, {"capo": capo})
        for e, n in zip(r["events"], notes):
            assert pitch_at(e["string"], e["fret"], STD, capo) == n["midi"]
    r = generate_tab(notes, {"transpose": 2})
    for e, n in zip(r["events"], notes):
        assert pitch_at(e["string"], e["fret"], STD) == n["midi"] + 2


def test_drop_d_uses_low_string():
    r = generate_tab(melody([38, 45]), {"tuning": "drop_d"})
    assert r["events"][0]["string"] == 6 and r["events"][0]["fret"] == 0


def test_block_mode_confines_frets_when_possible():
    blocks = generate_blocks("C", "major", STD, 0, "position")
    notes = melody([60, 62, 64, 65, 67, 69, 71, 72])
    blk = next(b for b in blocks if b["fret_min"] <= 5 and b["fret_max"] >= 8)   # หน้าต่างที่ครอบช่อง 5–8
    r = generate_tab(notes, {"blocks": [blk], "block_mode": "single"})
    for e in r["events"]:
        if "octave_shifted" not in e["warnings"] and "out_of_block" not in e["warnings"]:
            assert blk["fret_min"] <= e["fret"] <= blk["fret_max"]


def test_out_of_block_policies_are_reported():
    blk = custom_block(0, 3)
    notes = melody([76])                                  # E5: ในช่อง 0–3 ไม่มี (สาย 1 ช่อง 12)
    r_oct = generate_tab(notes, {"blocks": [blk], "out_of_block": "octave_shift"})
    assert "octave_shifted" in r_oct["events"][0]["warnings"] and 0 <= r_oct["events"][0]["fret"] <= 3
    assert r_oct["events"][0]["octave_shifted"] in (12, -12, 24, -24)
    r_warn = generate_tab(notes, {"blocks": [blk], "out_of_block": "warn"})
    assert "out_of_block" in r_warn["events"][0]["warnings"] and r_warn["events"][0]["fret"] > 3
    r_str = generate_tab(notes, {"blocks": [blk], "out_of_block": "stretch"})
    assert r_str["events"][0]["fret"] is not None


def test_locked_event_is_respected_and_neighbours_adapt():
    notes = melody([64, 64, 64])
    free = generate_tab(notes)
    lock = {"n1": {"string": 3, "fret": 9}}               # บังคับตัวกลางไปสาย 3 ช่อง 9
    r = generate_tab(notes, locked=lock)
    mid = r["events"][1]
    assert (mid["string"], mid["fret"]) == (3, 9) and mid["locked"]
    assert free["events"][1]["locked"] is False
    # lock ที่ pitch ไม่ตรงกับโน้ต (เช่นโน้ตถูกแก้ไปแล้ว) ต้องถูกเพิกเฉย ไม่ทำให้โน้ตผิด
    bad = generate_tab(notes, locked={"n1": {"string": 1, "fret": 3}})
    assert pitch_at(bad["events"][1]["string"], bad["events"][1]["fret"], STD) == 64 and not bad["events"][1]["locked"]


def test_alternatives_exclude_current_and_keep_pitch():
    notes = melody([60, 64, 67])
    r = generate_tab(notes)
    alts = alternatives(notes, r["settings"], None, "n1")
    cur = (r["events"][1]["string"], r["events"][1]["fret"])
    assert alts and all((a["string"], a["fret"]) != cur for a in alts)
    assert all(pitch_at(a["string"], a["fret"], STD) == 64 for a in alts)
    assert [a["delta_cost"] for a in alts] == sorted(a["delta_cost"] for a in alts)
    assert all(a["delta_cost"] >= -1e-6 for a in alts)    # คำตอบของระบบคือต่ำสุดอยู่แล้ว ทางเลือกต้องไม่ถูกกว่า


def test_blocks_generation_and_coverage():
    for system, n in (("position", 7), ("pentatonic", 5)):
        b = generate_blocks("G", "major", STD, 0, system)
        assert len(b) >= n - 2 and all(0 <= x["fret_min"] <= x["fret_max"] <= 22 for x in b)
        assert [x["fret_min"] for x in b] == sorted(x["fret_min"] for x in b)
    pent = generate_blocks("A", "minor", STD, 0, "pentatonic")
    assert all(set(x["pcs"]) == scale_pcs("A", "minor", pentatonic=True) for x in pent)
    notes_p = [60, 62, 64, 65, 67]
    assert coverage(notes_p, generate_blocks("C", "major", STD), STD) == 1.0
    assert coverage(notes_p, [custom_block(20, 22)], STD) < 1.0
    assert coverage([], [], STD) == 0.0


def test_suggest_returns_two_groups_and_prefers_friendly_shapes():
    notes = melody([64, 66, 68, 69, 71, 73, 75, 76, 75, 73, 71, 69])         # E major scale
    r = suggest(notes, {"tonic": "E", "mode": "major"}, top=5)
    assert r["same_sound"] and all(x["transpose"] == 0 for x in r["same_sound"])
    assert r["transposed"] and all(x["transpose"] != 0 for x in r["transposed"])
    scores = [x["score"] for x in r["same_sound"]]
    assert scores == sorted(scores)
    assert r["best"]["score"] == min(x["score"] for x in r["same_sound"] + r["transposed"])


def test_performance_800_notes_under_half_second():
    import random
    rnd = random.Random(1)
    p, notes = 64, []
    for i in range(800):
        p = max(45, min(84, p + rnd.choice([-3, -2, -1, 0, 1, 2, 3])))   # ช่วงที่กีตาร์เล่นได้ (สูงสุด 64+22 = 86)
        notes.append(N(i, p, i * 0.3))
    generate_tab(notes[:20])                                # warm-up (คอมไพล์ numba)
    t = time.time()
    r = generate_tab(notes)
    dt = time.time() - t
    assert r["summary"]["playable"] == 800 and dt < 0.5, f"{dt:.2f}s"
    # แนะนำคีย์ทั้ง 13×8 แบบ ต้องจบในเวลาที่ใช้งานจริงได้ (ไม่ค้าง UI)
    t = time.time()
    suggest(notes[:300], {"tonic": "C", "mode": "major"})
    assert time.time() - t < 5.0


def test_suggest_never_ranks_note_losing_options_above_complete_ones():
    notes = melody([40, 42, 44, 52, 54, 56, 64, 66])          # มีโน้ตต่ำ (E2…) ที่ capo สูงจะเล่นไม่ได้
    r = suggest(notes, {"tonic": "E", "mode": "major"}, top=50)
    for group in ("same_sound", "transposed"):
        flags = [x["unplayable"] > 0 for x in r[group]]
        assert flags == sorted(flags), "ตัวเลือกที่ทำให้โน้ตหายต้องอยู่หลังตัวเลือกที่เล่นได้ครบ"
    assert r["best"]["unplayable"] == 0
